#include <map>
#include <string>

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "yaml-config.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("LEO-Satellite-Sim");

void run(YAML::Node config) {
  NodeContainer nodes;

  // Track how many links created
  int linkCounter = 0;

  // Read nodes from file and store in above data structures
  auto configNodes = config["topology"]["nodes"];
  for (const auto& node : configNodes) {
    Ptr<Node> newNode = CreateObject<Node>();
    std::string nodeName = node["name"].as<std::string>();
    
    // Map Node to Name
    Names::Add(node["name"].as<std::string>(), newNode);

    nodes.Add(newNode);
  }

  InternetStackHelper internetStack;
  internetStack.Install(nodes);

  // Create links from config
  auto configLinks = config["topology"]["links"];
  for (const auto& link : configLinks) {
    // Get nodes for this link
    std::string sourceName = link["source"].as<std::string>();
    std::string targetName = link["target"].as<std::string>();

    NodeContainer linkNodes;
    linkNodes.Add(Names::Find<Node>(sourceName));
    linkNodes.Add(Names::Find<Node>(targetName));

    NS_LOG_UNCOND("Creating link from "
                << sourceName << " to " << targetName << " with rate "
                << link["data_rate"].as<std::string>() << " and delay "
                << link["delay"].as<std::string>());
    // Create Point to Point link with params from config
    PointToPointHelper p2p;
    p2p.SetQueue("ns3::DropTailQueue");
    p2p.SetDeviceAttribute("DataRate",
                            StringValue(link["data_rate"].as<std::string>()));
    p2p.SetChannelAttribute("Delay",
                            StringValue(link["delay"].as<std::string>()));

    // Install devices for this link
    NetDeviceContainer linkDevices = p2p.Install(linkNodes);

    // Setup IP addresses for this link
    Ipv4AddressHelper ipv4;
    // Generate unique subnet for each link
    std::string subnet =
        "10.1." + std::to_string(linkCounter++) + ".0";
    ipv4.SetBase(subnet.c_str(), "255.255.255.0");
    ipv4.Assign(linkDevices);
  }

  Simulator::Run();
  Simulator::Destroy();
}

int main(int argc, char* argv[]) {
  std::string configFile;
  CommandLine cmd;
  cmd.AddValue("config", "Path to YAML config file", configFile);
  cmd.Parse(argc, argv);

  LogComponentEnableAll(LOG_LEVEL_ERROR);

  try {
    auto config = ReadYamlConfig(configFile);
    NS_LOG_UNCOND("Successfully read YAML config:");
    run(config);
  } catch (const std::exception& e) {
    NS_LOG_ERROR("Failed to read config: " << e.what());
    return 1;
  }

  return 0;
}