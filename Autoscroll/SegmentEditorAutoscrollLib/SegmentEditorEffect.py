import os
import vtk, qt, ctk, slicer
import logging
from SegmentEditorEffects import *

class SegmentEditorEffect(AbstractScriptedSegmentEditorEffect):
  """This effect uses Watershed algorithm to partition the input volume"""

  def __init__(self, scriptedEffect):
    scriptedEffect.name = 'Autoscroll'
    scriptedEffect.perSegment = False # this effect operates on all segments at once (not on a single selected segment)
    AbstractScriptedSegmentEditorEffect.__init__(self, scriptedEffect)

  def clone(self):
    # It should not be necessary to modify this method
    import qSlicerSegmentationsEditorEffectsPythonQt as effects
    clonedEffect = effects.qSlicerSegmentEditorScriptedEffect(None)
    clonedEffect.setPythonSource(__file__.replace('\\','/'))
    return clonedEffect

  def icon(self):
    # It should not be necessary to modify this method
    iconPath = os.path.join(os.path.dirname(__file__), 'SegmentEditorEffect.png')
    if os.path.exists(iconPath):
      return qt.QIcon(iconPath)
    return qt.QIcon()

  def helpText(self):
    return """<html>This module autoscrolls through slices to help with segmentation<br>.
It does not alter the segmentation nor volumes in any way, and it restores the view when autoscrolling is stopped
<p><ul style="margin: 0">
<li><b>Alt+C:</b> Start scrolling</li>
<li><b>Ctrl+Alt+C:</b> Set parameters</li>
</ul></p></html>"""

  def setupOptionsFrame(self):

     # Autoscroll range slider
    self.autoscrollRangeSlider = slicer.qMRMLSliderWidget()
    self.autoscrollRangeSlider.setMRMLScene(slicer.mrmlScene)
    self.autoscrollRangeSlider.minimum = 1
    self.autoscrollRangeSlider.maximum = 10
    self.autoscrollRangeSlider.decimals = 0
    self.autoscrollRangeSlider.value = 5
    self.autoscrollRangeSlider.suffix = " slices"
    self.autoscrollRangeSlider.setToolTip('How many slices you would like to autoscroll up and down')
    self.scriptedEffect.addLabeledOptionsWidget("Slice range:", self.autoscrollRangeSlider)

     # Autoscroll speed slider
    self.autoscrollSpeedSliderFps = slicer.qMRMLSliderWidget()
    self.autoscrollSpeedSliderFps.setMRMLScene(slicer.mrmlScene)
    self.autoscrollSpeedSliderFps.minimum = 1
    self.autoscrollSpeedSliderFps.maximum = 100
    self.autoscrollSpeedSliderFps.value = 20
    self.autoscrollSpeedSliderFps.suffix = " fps"
    self.autoscrollSpeedSliderFps.setToolTip('How many slices you want to autoscroll per second')
    self.scriptedEffect.addLabeledOptionsWidget("Slice speed:", self.autoscrollSpeedSliderFps)

    # Input view selector
    self.sliceNodeSelector = qt.QComboBox()
    self.sliceNodeSelector.setToolTip("This slice will be excluded during autoscrolling.")
    self.scriptedEffect.addLabeledOptionsWidget("Exclude view:", self.sliceNodeSelector)

    # Start button
    self.applyButton = qt.QPushButton("Start")
    self.applyButton.objectName = self.__class__.__name__ + 'Start'
    self.applyButton.setToolTip("Start/Stop autoscrolling (Alt+C)")
    self.scriptedEffect.addOptionsWidget(self.applyButton)

    # Set Hotkeys
    self.hotkey = qt.QShortcut(qt.QKeySequence("Alt+C"), slicer.util.mainWindow())
    self.hotkey2 = qt.QShortcut(qt.QKeySequence("Ctrl+Alt+C"), slicer.util.mainWindow())

    # Connections
    self.applyButton.connect('clicked()', self.onApply)
    self.autoscrollRangeSlider.connect("valueChanged(double)", self.updateMRMLFromGUI)
    self.autoscrollSpeedSliderFps.connect("valueChanged(double)", self.updateMRMLFromGUI)
    self.sliceNodeSelector.connect("currentIndexChanged(int)", self.updateMRMLFromGUI)
    self.hotkey.connect('activated()', self.autoscrollHotkey)
    self.hotkey2.connect('activated()', self.openSettings)

    self.timer = qt.QTimer()
    self.timer.setSingleShot(False)
    self.timer.setInterval(100)
    self.timer.connect('timeout()', self.switchSlice)

    # Initialize variables
    self.animate = False

    self.sliceViewNames = ['Yellow', 'Green', 'Red']

    self.sliceObservations = []
    self.observeSliceOffsetChange = True
    self.originalSliceOffsets = {}

    # None, Red, Yellow, Green
    self.sliceNodeSelector.addItems(['None'] + self.sliceViewNames[2:] + self.sliceViewNames[:2])
  
  def createCursor(self, widget):
    # Turn off effect-specific cursor for this effect
    return slicer.util.mainWindow().cursor

  def setMRMLDefaults(self):
    self.scriptedEffect.setParameterDefault("ScrollRangeSlice", 5)
    self.scriptedEffect.setParameterDefault("ScrollSpeedFps", 20.0)
    self.scriptedEffect.setParameterDefault("ExcludeView", "")

  def updateGUIFromMRML(self):
    wasBlocked = self.autoscrollRangeSlider.blockSignals(True)
    self.autoscrollRangeSlider.setValue(self.scriptedEffect.integerParameter("ScrollRangeSlice"))
    self.autoscrollRangeSlider.blockSignals(wasBlocked)

    wasBlocked = self.autoscrollSpeedSliderFps.blockSignals(True)
    self.autoscrollSpeedSliderFps.setValue(self.scriptedEffect.doubleParameter("ScrollSpeedFps"))
    self.autoscrollSpeedSliderFps.blockSignals(wasBlocked)

    wasBlocked = self.sliceNodeSelector.blockSignals(True)
    self.sliceNodeSelector.setCurrentText(self.scriptedEffect.parameter("ExcludeView"))
    self.sliceNodeSelector.blockSignals(wasBlocked)

    fps = max(self.scriptedEffect.doubleParameter("ScrollSpeedFps"), 0.1)
    self.timer.setInterval(1000.0/fps)

  def updateMRMLFromGUI(self):
    self.scriptedEffect.setParameter("ScrollRangeSlice", int(self.autoscrollRangeSlider.value))
    self.scriptedEffect.setParameter("ScrollSpeedFps", self.autoscrollSpeedSliderFps.value)
    self.scriptedEffect.setParameter("ExcludeView", self.sliceNodeSelector.currentText) 
  
  def autoscrollHotkey(self):
    if self.applyButton.enabled:
      self.onApply()

  def openSettings(self):
    slicer.util.mainWindow().moduleSelector().selectModule('SegmentEditor')
    self.scriptedEffect.selectEffect("Autoscroll")

  def masterVolumeNodeChanged(self):
    self.updateGUIFromMRML()

  def onSliceNodeModified(self, caller, event):
    if not self.observeSliceOffsetChange:
      return
    for sliceViewName in self.sliceViewNames:
      self.originalSliceOffsets[sliceViewName] = slicer.app.layoutManager().sliceWidget(sliceViewName).sliceLogic().GetSliceNode().GetSliceOffset()
    # After slice position is manually modified, reset step and wait a bit more
    self.step = 0
    self.switchSlice()
    self.timer.setInterval(1000.0)

  def addSliceObservers(self):
    for sliceViewName in self.sliceViewNames:
        sliceNode = slicer.app.layoutManager().sliceWidget(sliceViewName).sliceLogic().GetSliceNode()
        self.sliceObservations.append([sliceNode, sliceNode.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onSliceNodeModified)])

  def removeSliceObservers(self):
    for sliceObservation in self.sliceObservations:
      sliceObservation[0].RemoveObserver(sliceObservation[1])
    self.sliceObservations = []

  def onApply(self):
    self.animate = not self.animate
    self.applyButton.text = "Stop" if self.animate else "Start"

    if not self.animate:
      self.timer.stop()
      # Restore original view to before button was pressed
      self.observeSliceOffsetChange = False
      self.removeSliceObservers()
      for sliceViewName in self.sliceViewNames:
        slicer.app.layoutManager().sliceWidget(sliceViewName).sliceLogic().GetSliceNode().SetSliceOffset(self.originalSliceOffsets[sliceViewName])
      self.observeSliceOffsetChange = True
    else:
      self.addSliceObservers()
      self.originalSliceOffsets = {}
      for sliceViewName in self.sliceViewNames:
        self.originalSliceOffsets[sliceViewName] = slicer.app.layoutManager().sliceWidget(sliceViewName).sliceLogic().GetSliceNode().GetSliceOffset()
      self.step = 0
      self.stepIncrement = 1
      self.timer.start()

  def switchSlice(self):
    self.observeSliceOffsetChange = False

    excludedSlice = self.scriptedEffect.parameter("ExcludeView")
    for sliceViewName in self.sliceViewNames:
      if sliceViewName == excludedSlice:
        continue
      sliceLogic = slicer.app.layoutManager().sliceWidget(sliceViewName).sliceLogic()
      spacing = sliceLogic.GetLowestVolumeSliceSpacing()
      offset = self.originalSliceOffsets[sliceViewName] + self.step * spacing[2]
      sliceLogic.GetSliceNode().SetSliceOffset(offset)

    # When slice is manually moved then scroll speed is temporarily increased.
    # Restore it now.
    fps = max(self.scriptedEffect.doubleParameter("ScrollSpeedFps"), 0.1)
    self.timer.setInterval(1000.0/fps)

    stepRange = self.scriptedEffect.integerParameter("ScrollRangeSlice")
    if self.step >= stepRange:
      self.stepIncrement = -1
    elif self.step <= -stepRange:
      self.stepIncrement = +1
    self.step += self.stepIncrement

    self.observeSliceOffsetChange = True
