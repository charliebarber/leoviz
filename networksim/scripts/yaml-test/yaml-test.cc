#include "yaml-config.h"
#include "ns3/core-module.h"
#include <string>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("YamlTest");

int main(int argc, char* argv[])
{
    std::string configFile = "scratch/yaml-test/config.yaml";
    
    CommandLine cmd;
    cmd.AddValue("config", "Path to YAML config file", configFile);
    cmd.Parse(argc, argv);
    
    try {
        auto config = ReadYamlConfig(configFile);
        NS_LOG_UNCOND("Successfully read YAML config:");
        NS_LOG_UNCOND("Test value: " << config["test"]["value"].as<std::string>());
    } catch (const std::exception& e) {
        NS_LOG_ERROR("Failed to read config: " << e.what());
        return 1;
    }

    Simulator::Run();
    Simulator::Destroy();
    return 0;
}