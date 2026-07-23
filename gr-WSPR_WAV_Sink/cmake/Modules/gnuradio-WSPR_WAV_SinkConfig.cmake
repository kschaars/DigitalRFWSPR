find_package(PkgConfig)

PKG_CHECK_MODULES(PC_GR_WSPR_WAV_SINK gnuradio-WSPR_WAV_Sink)

FIND_PATH(
    GR_WSPR_WAV_SINK_INCLUDE_DIRS
    NAMES gnuradio/WSPR_WAV_Sink/api.h
    HINTS $ENV{WSPR_WAV_SINK_DIR}/include
        ${PC_WSPR_WAV_SINK_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    GR_WSPR_WAV_SINK_LIBRARIES
    NAMES gnuradio-WSPR_WAV_Sink
    HINTS $ENV{WSPR_WAV_SINK_DIR}/lib
        ${PC_WSPR_WAV_SINK_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/gnuradio-WSPR_WAV_SinkTarget.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GR_WSPR_WAV_SINK DEFAULT_MSG GR_WSPR_WAV_SINK_LIBRARIES GR_WSPR_WAV_SINK_INCLUDE_DIRS)
MARK_AS_ADVANCED(GR_WSPR_WAV_SINK_LIBRARIES GR_WSPR_WAV_SINK_INCLUDE_DIRS)
