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
    self.cartoonRangeSlider.value = 2
    self.cartoonRangeSlider.setToolTip('Increasing this value smooths the segmentation and reduces leaks. This is the sigma used for edge detection.')
    self.scriptedEffect.addLabeledOptionsWidget("Slice range:", self.cartoonRangeSlider)
    self.cartoonRangeSlider.connect('valueChanged(double)', self.updateMRMLFromGUI)


     # Cartoon speed slider
    self.cartoonSpeedSlider = slicer.qMRMLSliderWidget()
    self.cartoonSpeedSlider.setMRMLScene(slicer.mrmlScene)
    self.cartoonSpeedSlider.minimum = 0
    self.cartoonSpeedSlider.maximum = 10
    self.cartoonSpeedSlider.value = 2
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

  def createCursor(self, widget):
    # Turn off effect-specific cursor for this effect
    return slicer.util.mainWindow().cursor

  def setMRMLDefaults(self):
    self.scriptedEffect.setParameterDefault("ObjectScaleMm", 2.0)

  def updateGUIFromMRML(self):
    pass

  def updateMRMLFromGUI(self):
    pass

  def onCancelRequested(self):
    self.cancelRequested = not self.cancelRequested
    self.applyButton.text = "Apply" if self.cancelRequested else "Cancel"

  def onApply(self):
    self.onCancelRequested()

    if self.cancelRequested:
        # Revert to original view
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

        # Get period
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


  def onApply2(self):

    # Get list of visible segment IDs, as the effect ignores hidden segments.
    segmentationNode = self.scriptedEffect.parameterSetNode().GetSegmentationNode()
    visibleSegmentIds = vtk.vtkStringArray()
    segmentationNode.GetDisplayNode().GetVisibleSegmentIDs(visibleSegmentIds)
    if visibleSegmentIds.GetNumberOfValues() == 0:
      logging.info("Smoothing operation skipped: there are no visible segments")
      return

    # This can be a long operation - indicate it to the user
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

    # Allow users revert to this state by clicking Undo
    self.scriptedEffect.saveStateForUndo()

    # Export master image data to temporary new volume node.
    # Note: Although the original master volume node is already in the scene, we do not use it here,
    # because the master volume may have been resampled to match segmentation geometry.
    import vtkSegmentationCorePython as vtkSegmentationCore
    masterVolumeNode = slicer.vtkMRMLScalarVolumeNode()
    slicer.mrmlScene.AddNode(masterVolumeNode)
    masterVolumeNode.SetAndObserveTransformNodeID(segmentationNode.GetTransformNodeID())
    slicer.vtkSlicerSegmentationsModuleLogic.CopyOrientedImageDataToVolumeNode(self.scriptedEffect.masterVolumeImageData(), masterVolumeNode)
    # Generate merged labelmap of all visible segments, as the filter expects a single labelmap with all the labels.
    mergedLabelmapNode = slicer.vtkMRMLLabelMapVolumeNode()
    slicer.mrmlScene.AddNode(mergedLabelmapNode)
    slicer.vtkSlicerSegmentationsModuleLogic.ExportSegmentsToLabelmapNode(segmentationNode, visibleSegmentIds, mergedLabelmapNode, masterVolumeNode)

    # Run segmentation algorithm
    import SimpleITK as sitk
    import sitkUtils
    # Read input data from Slicer into SimpleITK
    labelImage = sitk.ReadImage(sitkUtils.GetSlicerITKReadWriteAddress(mergedLabelmapNode.GetName()))
    backgroundImage = sitk.ReadImage(sitkUtils.GetSlicerITKReadWriteAddress(masterVolumeNode.GetName()))
    # Run watershed filter
    featureImage = sitk.GradientMagnitudeRecursiveGaussian(backgroundImage, float(self.scriptedEffect.doubleParameter("ObjectScaleMm")))
    del backgroundImage
    f = sitk.MorphologicalWatershedFromMarkersImageFilter()
    f.SetMarkWatershedLine(False)
    f.SetFullyConnected(False)
    labelImage = f.Execute(featureImage, labelImage)
    del featureImage
    # Pixel type of watershed output is the same as the input. Convert it to int16 now.
    if labelImage.GetPixelID() != sitk.sitkInt16:
      labelImage = sitk.Cast(labelImage, sitk.sitkInt16)
    # Write result from SimpleITK to Slicer. This currently performs a deep copy of the bulk data.
    sitk.WriteImage(labelImage, sitkUtils.GetSlicerITKReadWriteAddress(mergedLabelmapNode.GetName()))
    mergedLabelmapNode.GetImageData().Modified()
    mergedLabelmapNode.Modified()

    # Update segmentation from labelmap node and remove temporary nodes
    slicer.vtkSlicerSegmentationsModuleLogic.ImportLabelmapToSegmentationNode(mergedLabelmapNode, segmentationNode, visibleSegmentIds)
    slicer.mrmlScene.RemoveNode(masterVolumeNode)
    slicer.mrmlScene.RemoveNode(mergedLabelmapNode)

    qt.QApplication.restoreOverrideCursor()
