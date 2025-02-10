#ifndef YAML_CONFIG_H
#define YAML_CONFIG_H

#include <yaml-cpp/yaml.h>
#include <string>

YAML::Node ReadYamlConfig(const std::string& filename);

#endif