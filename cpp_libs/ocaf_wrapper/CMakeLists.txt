CMAKE_MINIMUM_REQUIRED(VERSION 3.16)

PROJECT(occutils)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin/bin/bin/bin")
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_CURRENT_SOURCE_DIR}/cmake/modules")

#Find opencascade libraries
FIND_PACKAGE(OCC REQUIRED)
if (NOT OCC_FOUND)
    message(FATAL_ERROR "OCC Not found")
endif()

find_package(SWIG 4.1.1 REQUIRED)
include(UseSWIG)

message("OCE_FOUND? <${OCE_FOUND}>")
message("OCC_FOUND? <${OCC_FOUND}>")
message("OCC INCLUDE DIR: <${OCC_INCLUDE_DIR}>")
message("OCC Libraries: <${OCC_LIBRARIES}>")

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)

add_library(ocaf_wrapper INTERFACE inc/ocaf_wrapper.h)

target_link_libraries(ocaf_wrapper
        INTERFACE
        ${Boost_LIBRARIES}
        ${OCC_LIBRARIES}
        ${OCC_OCAF_LIBRARIES}
        ${Python3_LIBRARIES})

target_include_directories(ocaf_wrapper
        INTERFACE
        ${CMAKE_CURRENT_SOURCE_DIR}/inc
        ${OCC_INCLUDE_DIR}
        ${Python3_INCLUDE_DIRS})

set_property(SOURCE swig/ocaf_wrapper.i PROPERTY CPLUSPLUS ON)
swig_add_library(ocaf_wrapper_swig LANGUAGE python SOURCES swig/ocaf_wrapper.i TYPE SHARED)
set_target_properties(ocaf_wrapper_swig
        PROPERTIES
        SWIG_USE_TARGET_INCLUDE_DIRECTORIES TRUE
        SWIG_COMPILE_OPTIONS "-py3;-includeall;-DSWIG_TYPE_TABLE=ocaf_wrapper")
swig_link_libraries(ocaf_wrapper_swig ocaf_wrapper Python3::Module)

execute_process(COMMAND ${Python3_EXECUTABLE} -c "from distutils.sysconfig import get_python_lib; import os;print(get_python_lib())" OUTPUT_VARIABLE python_lib OUTPUT_STRIP_TRAILING_WHITESPACE)

install(TARGETS ocaf_wrapper_swig DESTINATION ${python_lib}/ocaf_wrapper_swig)
install(FILES ${CMAKE_BINARY_DIR}/ocaf_wrapper.py DESTINATION ${python_lib}/ocaf_wrapper_swig RENAME __init__.py)
#install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/swig/__init__.py DESTINATION ${python_lib}/occutils)

