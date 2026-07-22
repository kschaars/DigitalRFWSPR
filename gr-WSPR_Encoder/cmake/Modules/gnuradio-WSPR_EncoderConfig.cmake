find_package(PkgConfig)

PKG_CHECK_MODULES(PC_GR_WSPR_ENCODER gnuradio-WSPR_Encoder)

FIND_PATH(
    GR_WSPR_ENCODER_INCLUDE_DIRS
    NAMES gnuradio/WSPR_Encoder/api.h
    HINTS $ENV{WSPR_ENCODER_DIR}/include
        ${PC_WSPR_ENCODER_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    GR_WSPR_ENCODER_LIBRARIES
    NAMES gnuradio-WSPR_Encoder
    HINTS $ENV{WSPR_ENCODER_DIR}/lib
        ${PC_WSPR_ENCODER_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/gnuradio-WSPR_EncoderTarget.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GR_WSPR_ENCODER DEFAULT_MSG GR_WSPR_ENCODER_LIBRARIES GR_WSPR_ENCODER_INCLUDE_DIRS)
MARK_AS_ADVANCED(GR_WSPR_ENCODER_LIBRARIES GR_WSPR_ENCODER_INCLUDE_DIRS)
