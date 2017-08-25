import os
import vtk, qt, ctk, slicer
import logging
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
    return """This module cartoons through slices to help with segmentation
"""

  def setupOptionsFrame(self):

     # Cartoon range slider
    self.cartoonRangeSlider = slicer.qMRMLSliderWidget()
    self.cartoonRangeSlider.setMRMLScene(slicer.mrmlScene)
    self.cartoonRangeSlider.minimum = 0
    self.cartoonRangeSlider.maximum = 10
    self.cartoonRangeSlider.value = 5
    self.cartoonRangeSlider.setToolTip('Increasing this value smooths the segmentation and reduces leaks. This is the sigma used for edge detection.')
    self.scriptedEffect.addLabeledOptionsWidget("Slice range:", self.cartoonRangeSlider)
    self.cartoonRangeSlider.connect('valueChanged(double)', self.updateMRMLFromGUI)


     # Cartoon speed slider
    self.cartoonSpeedSlider = slicer.qMRMLSliderWidget()
    self.cartoonSpeedSlider.setMRMLScene(slicer.mrmlScene)
    self.cartoonSpeedSlider.minimum = 1
    self.cartoonSpeedSlider.maximum = 100
    self.cartoonSpeedSlider.value = 20
    self.cartoonSpeedSlider.setToolTip('Increasing this value smooths the segmentation and reduces leaks. This is the sigma used for edge detection.')
    self.scriptedEffect.addLabeledOptionsWidget("Slice speed:", self.cartoonSpeedSlider)
    self.cartoonSpeedSlider.connect('valueChanged(double)', self.updateMRMLFromGUI)

    # Apply button
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.objectName = self.__class__.__name__ + 'Apply'
    self.applyButton.setToolTip("Accept previewed result")
    self.scriptedEffect.addOptionsWidget(self.applyButton)
    self.applyButton.connect('clicked()', self.onApply)

    self.cancelRequested = True

    self.colorsRAS = ['Yellow', 'Green', 'Red']

    self.hotkey = qt.QShortcut(qt.QKeySequence("Ctrl+Shift+C"), slicer.util.mainWindow())
    self.hotkey.connect('activated()', self.onApply)
    self.hotkey2 = qt.QShortcut(qt.QKeySequence("Ctrl+Alt+Shift+C"), slicer.util.mainWindow())
    self.hotkey2.connect('activated()', self.onAltKey)

  def onAltKey(self):
    self.scriptedEffect.selectEffect("Cartooner")

  def createCursor(self, widget):
    # Turn off effect-specific cursor for this effect
    return slicer.util.mainWindow().cursor

  def masterVolumeNodeChanged(self):
    self.updateGUIFromMRML()

  def setMRMLDefaults(self):
    pass

  def updateGUIFromMRML(self):
    masterVolumeNode = self.scriptedEffect.parameterSetNode().GetMasterVolumeNode()
    bounds = [0] * 6
    masterVolumeNode.GetBounds(bounds)

    currentOffsets = {}
    ranges = []

    for i in range(len(self.colorsRAS)):
        color = self.colorsRAS[i]
        currentOffsets[color] = slicer.app.layoutManager().sliceWidget(color).sliceLogic().GetSliceOffset()
        # Get range from min bound
        ranges.append(currentOffsets[color] - bounds[i*2])
        # Get range from max bound
        ranges.append(bounds[i*2+1] - currentOffsets[color])

    minRange = min(ranges)
    minColorIndex = (ranges.index(minRange) - 1) / 2

    if(minRange < 0 or minColorIndex < 0):
        logging.error("Offset error, please contact the extension developer for support")
        return

    else:
        self.cartoonRangeSlider.minimum = 1
        self.cartoonRangeSlider.maximum = minRange / masterVolumeNode.GetSpacing()[minColorIndex]

  def updateMRMLFromGUI(self):
    pass

  def onCancelRequested(self):
    self.cancelRequested = not self.cancelRequested
    self.applyButton.text = "Apply" if self.cancelRequested else "Cancel"

  def onApply(self):
    self.onCancelRequested()

    if self.cancelRequested:
        # Restore original view to before button was pressed
        for color in self.colorsRAS:
            slicer.app.layoutManager().sliceWidget(color).sliceLogic().SetSliceOffset(self.originalRAS[color])

    else:
        pathToCursor = os.path.join(os.path.dirname(__file__), 'cursor.png')
        pixelMap = qt.QPixmap(pathToCursor)
        cursor = qt.QCursor(pixelMap)

        qt.QApplication.setOverrideCursor(cursor)

        import threading
        self.originalRAS = {}
        for color in self.colorsRAS:
            self.originalRAS[color] = slicer.app.layoutManager().sliceWidget(color).sliceLogic().GetSliceOffset()

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

        while not self.cancelRequested:
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
        slicer.app.layoutManager().sliceWidget(color).sliceLogic().SetSliceOffset(self.steps[color][self.currentStepIndex[color]])
