# Copyright 2020 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

########################################################################
# Check if there is C++ code at all
########################################################################
if(NOT WSPR_WAV_Sink_sources)
    message(STATUS "No C++ sources... skipping python bindings")
    return()
endif(NOT WSPR_WAV_Sink_sources)

########################################################################
# Check for pygccxml
########################################################################
gr_python_check_module_raw("pygccxml" "import pygccxml" PYGCCXML_FOUND)

include(GrPybind)

########################################################################
# Python Bindings
########################################################################

list(APPEND WSPR_WAV_Sink_python_files python_bindings.cc)

gr_pybind_make_oot(WSPR_WAV_Sink ../../.. gr::WSPR_WAV_Sink "${WSPR_WAV_Sink_python_files}")

# copy bindings extension for use in QA test module
add_custom_command(
    TARGET WSPR_WAV_Sink_python
    POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:WSPR_WAV_Sink_python>
            ${PROJECT_BINARY_DIR}/test_modules/gnuradio/WSPR_WAV_Sink/)

install(
    TARGETS WSPR_WAV_Sink_python
    DESTINATION ${GR_PYTHON_DIR}/gnuradio/WSPR_WAV_Sink
    COMPONENT pythonapi)
