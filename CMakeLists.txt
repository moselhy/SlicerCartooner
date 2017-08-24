cmake_minimum_required(VERSION 3.5)

project(Cartooner)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "http://slicer.org/slicerWiki/index.php/Documentation/Nightly/Extensions/Cartooner")
set(EXTENSION_CATEGORY "Segmentation")
set(EXTENSION_CONTRIBUTORS "Mohamed Moselhy (Western University), a (a), (New item)")
set(EXTENSION_DESCRIPTION "Cartoon through slices using slice range and speed")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/Cartooner.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/Cartooner/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a space separated string, a list or 'NA' if any

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(Cartooner)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
