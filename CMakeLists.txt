cmake_minimum_required(VERSION 3.5)

project(Autoscroll)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/moselhy/SlicerAutoscroll")
set(EXTENSION_CATEGORY "Segmentation")
set(EXTENSION_CONTRIBUTORS "Mohamed Moselhy (Western University)")
set(EXTENSION_DESCRIPTION "Cartoon through slices using slice range and speed")
set(EXTENSION_ICONURL "https://github.com/moselhy/SlicerAutoscroll/raw/master/Autoscroll.png")
set(EXTENSION_SCREENSHOTURLS "https://github.com/moselhy/SlicerAutoscroll/raw/master/docs/screenshot.png")
set(EXTENSION_DEPENDS "NA") # Specified as a space separated string, a list or 'NA' if any

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(Autoscroll)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
