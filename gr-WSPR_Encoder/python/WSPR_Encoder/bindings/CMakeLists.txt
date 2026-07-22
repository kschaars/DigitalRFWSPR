# Copyright 2020 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

########################################################################
# Check if there is C++ code at all
########################################################################
if(NOT WSPR_Encoder_sources)
    message(STATUS "No C++ sources... skipping python bindings")
    return()
endif(NOT WSPR_Encoder_sources)

########################################################################
# Check for pygccxml
########################################################################
gr_python_check_module_raw("pygccxml" "import pygccxml" PYGCCXML_FOUND)

include(GrPybind)

########################################################################
# Python Bindings
########################################################################

list(APPEND WSPR_Encoder_python_files python_bindings.cc)

gr_pybind_make_oot(WSPR_Encoder ../../.. gr::WSPR_Encoder "${WSPR_Encoder_python_files}")

# copy bindings extension for use in QA test module
add_custom_command(
    TARGET WSPR_Encoder_python
    POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:WSPR_Encoder_python>
            ${PROJECT_BINARY_DIR}/test_modules/gnuradio/WSPR_Encoder/)

install(
    TARGETS WSPR_Encoder_python
    DESTINATION ${GR_PYTHON_DIR}/gnuradio/WSPR_Encoder
    COMPONENT pythonapi)
