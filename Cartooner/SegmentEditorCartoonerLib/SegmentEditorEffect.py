import os
import vtk, qt, ctk, slicer
import logging, threading
from SegmentEditorEffects import *

class SegmentEditorEffect(AbstractScriptedSegmentEditorEffect):
  """This effect uses Watershed algorithm to partition the input volume"""

  def __init__(self, scriptedEffect):
    scriptedEffect.name = 'Cartooner'
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
    return """This module cartoons through slices to help with segmentation, press Alt+C to start cartooning or Ctrl+Alt+C to set parameters. It does not alter the segmentation nor volumes in any way, and it restores the view when cartooning is stopped
"""

  def setupOptionsFrame(self):

     # Cartoon range slider
    self.cartoonRangeSlider = slicer.qMRMLSliderWidget()
    self.cartoonRangeSlider.setMRMLScene(slicer.mrmlScene)
    self.cartoonRangeSlider.minimum = 0
    self.cartoonRangeSlider.maximum = 10
    self.cartoonRangeSlider.value = 5
    self.cartoonRangeSlider.setToolTip('How many slices you would like to cartoon up and down')
    self.scriptedEffect.addLabeledOptionsWidget("Slice range:", self.cartoonRangeSlider)


     # Cartoon speed slider
    self.cartoonSpeedSlider = slicer.qMRMLSliderWidget()
    self.cartoonSpeedSlider.setMRMLScene(slicer.mrmlScene)
    self.cartoonSpeedSlider.minimum = 1
    self.cartoonSpeedSlider.maximum = 100
    self.cartoonSpeedSlider.value = 20
    self.cartoonSpeedSlider.setToolTip('How many slices you want to cartoon per second')
    self.scriptedEffect.addLabeledOptionsWidget("Slice speed:", self.cartoonSpeedSlider)

    # Input view selector
    self.sliceNodeSelector = qt.QComboBox()
    self.sliceNodeSelector.setToolTip("This slice will be excluded during cartooning.")
    self.scriptedEffect.addLabeledOptionsWidget("Exclude view:", self.sliceNodeSelector)


    # Start button
    self.applyButton = qt.QPushButton("Start")
    self.applyButton.objectName = self.__class__.__name__ + 'Start'
    self.applyButton.setToolTip("Start/Stop cartooning (Alt+C)")
    self.scriptedEffect.addOptionsWidget(self.applyButton)

    # Set Hotkeys
    self.hotkey = qt.QShortcut(qt.QKeySequence("Alt+C"), slicer.util.mainWindow())
    self.hotkey2 = qt.QShortcut(qt.QKeySequence("Ctrl+Alt+C"), slicer.util.mainWindow())

    # Connections
    self.applyButton.connect('clicked()', self.onApply)
    self.sliceNodeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateGUIFromMRML)
    self.hotkey.connect('activated()', self.cartoonHotkey)
    self.hotkey2.connect('activated()', self.openSettings)

    # Initialize variables
    self.setupVariables()

  def setupVariables(self):
    self.runningStatus = False

    self.colorsRAS = ['Yellow', 'Green', 'Red']

    self.restoringViews = False
    self.currentOffsets = {}
    self.originalRAS = {}
    for color in self.colorsRAS:
        self.currentOffsets[color] = slicer.app.layoutManager().sliceWidget(color).sliceLogic().GetSliceNode().GetSliceOffset()
        self.originalRAS[color] = self.currentOffsets[color]

    self.sliceNodeSelector.addItems(['None'] + self.colorsRAS)
    self.updateMRMLFromGUI()
    

  def cartoonHotkey(self):
    if self.applyButton.enabled:
        self.onApply()

  def openSettings(self):
    slicer.util.mainWindow().moduleSelector().selectModule('SegmentEditor')
    self.scriptedEffect.selectEffect("Cartooner")

  def createCursor(self, widget):
    # Turn off effect-specific cursor for this effect
    return slicer.util.mainWindow().cursor

  def masterVolumeNodeChanged(self):
    self.updateGUIFromMRML()

  def onSliceLogicModifiedEvent(self, caller, event):
    for color in self.colorsRAS:
        sliceNode = slicer.app.layoutManager().sliceWidget(color).sliceLogic().GetSliceNode()
        if color != self.sliceNodeSelector.currentText:
            if sliceNode.GetSliceOffset() != self.currentOffsets[color]:
                self.updateGUIFromMRML()

  def setMRMLDefaults(self):
    pass

  def updateGUIFromMRML(self):
    if not self.runningStatus and not self.restoringViews:
        slicer.app.processEvents()
        bounds = [0] * 6
        masterVolumeNode = self.scriptedEffect.parameterSetNode().GetMasterVolumeNode()
        if masterVolumeNode:
            masterVolumeNode.GetBounds(bounds)

            ranges = []

            for i in range(len(self.colorsRAS)):
                color = self.colorsRAS[i]
                if color != self.sliceNodeSelector.currentText:
                    self.currentOffsets[color] = slicer.app.layoutManager().sliceWidget(color).sliceLogic().GetSliceNode().GetSliceOffset()
                    # Get range from min bound
                    minBound = self.currentOffsets[color] - bounds[i*2]
                    # Get range from max bound
                    maxBound = bounds[i*2+1] - self.currentOffsets[color]
                    # Get spacing of the current color
                    colorSpacing = masterVolumeNode.GetSpacing()[i]
                    # Parse ranges into their respective spacings
                    ranges.append(minBound / colorSpacing)
                    ranges.append(maxBound / colorSpacing)

            # Round ranges down
            ranges = [int(r) for r in ranges]

            minRange = min(ranges)

            self.applyButton.enabled = minRange > 0
            self.cartoonRangeSlider.minimum = 1
            self.cartoonRangeSlider.maximum = minRange


  def updateMRMLFromGUI(self):
    for color in self.colorsRAS:
        sliceNode = slicer.app.layoutManager().sliceWidget(color).sliceLogic().GetSliceNode()
        sliceNode.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onSliceLogicModifiedEvent)

  def onRunningStatusChanged(self):
    self.runningStatus = not self.runningStatus
    self.applyButton.text = "Stop" if self.runningStatus else "Start"

  def onApply(self):
    self.onRunningStatusChanged()

    if not self.runningStatus:
        self.restoringViews = True
        # Restore original view to before button was pressed
        for color in self.colorsRAS:
            slicer.app.layoutManager().sliceWidget(color).sliceLogic().GetSliceNode().SetSliceOffset(self.originalRAS[color])
        self.restoringViews = False

    else:
        pathToCursor = os.path.join(os.path.dirname(__file__), 'cursor.png')
        pixelMap = qt.QPixmap(pathToCursor)
        cursor = qt.QCursor(pixelMap)

        qt.QApplication.setOverrideCursor(cursor)

        self.originalRAS = {}
        for color in self.colorsRAS:
            self.originalRAS[color] = slicer.app.layoutManager().sliceWidget(color).sliceLogic().GetSliceNode().GetSliceOffset()

        masterVolumeNode = self.scriptedEffect.parameterSetNode().GetMasterVolumeNode()

        bounds = [0] * 6
        masterVolumeNode.GetBounds(bounds)

        # Get period (how many seconds to stay per slice)
        period = 1 / self.cartoonSpeedSlider.value

        self.steps = {}
        self.currentStepIndex = {}
        for i in range(len(self.colorsRAS)):
            color = self.colorsRAS[i]
            stepInterval = masterVolumeNode.GetSpacing()[i]
            maxOffset = stepInterval * self.cartoonRangeSlider.value
            start = self.originalRAS[color] - maxOffset
            stop = start + maxOffset * 2 + stepInterval
            self.steps[color] = range(int(start*1000), int(stop*1000), int(stepInterval*1000))
            self.steps[color] = [float(x) / 1000 for x in self.steps[color]]
            self.currentStepIndex[color] = len(self.steps[color]) / 2

        self.reverseStep = False
        timer = threading.Event()

        while self.runningStatus:
            self.stepThrough()
            timer.wait(period)
            slicer.app.processEvents()

        qt.QApplication.restoreOverrideCursor()


  def stepThrough(self):
    for color in self.colorsRAS:
        # If it is at the end, reverse playback
        if self.currentStepIndex[color] >= len(self.steps[color]) - 1:
            self.reverseStep = True
        # If it is in the beginning, normal playback
        elif self.currentStepIndex[color] == 0:
            self.reverseStep = False

        self.currentStepIndex[color] = self.currentStepIndex[color] - 1 if self.reverseStep else self.currentStepIndex[color] + 1
        if color != self.sliceNodeSelector.currentText:
            slicer.app.layoutManager().sliceWidget(color).sliceLogic().GetSliceNode().SetSliceOffset(self.steps[color][self.currentStepIndex[color]])
