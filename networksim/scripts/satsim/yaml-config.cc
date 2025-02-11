#include "yaml-config.h"
#include <fstream>

YAML::Node ReadYamlConfig(const std::string& filename) {
    return YAML::LoadFile(filename);
}