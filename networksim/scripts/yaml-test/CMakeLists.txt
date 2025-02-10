find_external_library(DEPENDENCY_NAME YAMLCPP
                     HEADER_NAME yaml-cpp/yaml.h
                     LIBRARY_NAME yaml-cpp)

build_exec(
    EXECNAME yaml-test
    SOURCE_FILES 
        yaml-test.cc
        yaml-config.cc
    HEADER_FILES
        yaml-config.h
    LIBRARIES_TO_LINK 
      ${YAMLCPP_LIBRARIES}
      ${libcore}
    EXECUTABLE_DIRECTORY_PATH ${CMAKE_OUTPUT_DIRECTORY}/scratch/yaml-test
)