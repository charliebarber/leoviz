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

  Ptr<Node> srcNode;
  Ptr<Node> dstNode;

  Config::SetDefault(
      "ns3::TcpL4Protocol::RecoveryType",
      TypeIdValue(TypeId::LookupByName("ns3::TcpClassicRecovery")));
  Config::SetDefault("ns3::TcpL4Protocol::SocketType",
                     StringValue("ns3::TcpLinuxReno"));
  // Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue(1073741824));
  // Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue(1073741824));
  // Set segment size of packet
  Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1446));
  // Enable/disable SACKs (disabled)
  Config::SetDefault("ns3::TcpSocketBase::Sack", BooleanValue(true));

  RngSeedManager::SetSeed(123456789);

  // Read nodes from file and store in above data structures
  auto configNodes = config["topology"]["nodes"];
  for (size_t i = 0; i < configNodes.size(); i++) {
    auto node = configNodes[i];
    Ptr<Node> newNode = CreateObject<Node>();
    std::string nodeName = node["name"].as<std::string>();

    // Map Node to Name
    Names::Add(node["name"].as<std::string>(), newNode);

    nodes.Add(newNode);

    // First node is the source
    if (i == 0) {
      srcNode = newNode;
    }
    // Last node is the destination
    if (i == configNodes.size() - 1) {
      dstNode = newNode;
    }
  }

  InternetStackHelper internetStack;
  internetStack.Install(nodes);

  Ipv4Address srcAddress;
  Ipv4Address dstAddress;

  // Create links from config
  auto configLinks = config["topology"]["links"];
  for (size_t i = 0; i < configLinks.size(); i++) {
    auto link = configLinks[i];
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
    std::string subnet = "10.1." + std::to_string(linkCounter++) + ".0";
    ipv4.SetBase(subnet.c_str(), "255.255.255.0");
    Ipv4InterfaceContainer interface = ipv4.Assign(linkDevices);

    // Save source and destination IP addresses
    // Only enable PCAPs on these nodes
    std::string pcapDir = "/home/charlie/fyp/leoviz/networksim/results/";
    if (i == 0) {
      srcAddress = interface.GetAddress(0);
      p2p.EnablePcap(pcapDir + "src_", linkDevices.Get(0));
    }
    if (i == configLinks.size() - 1) {
      dstAddress = interface.GetAddress(1);
      p2p.EnablePcap(pcapDir + "dst_", linkDevices.Get(1));
    }
  }

  // Setup TCP Experiments
  Ipv4GlobalRoutingHelper::PopulateRoutingTables();
  uint16_t port = 50000;
  // Install TCP sender on source node
  BulkSendHelper sendHelper("ns3::TcpSocketFactory",
                            InetSocketAddress(dstAddress, port));
  sendHelper.SetAttribute("MaxBytes", UintegerValue(0));
  sendHelper.SetAttribute("SendSize", UintegerValue(1024));
  auto tcpSender = sendHelper.Install(srcNode);

  // Install packet sink on destination node, receiving on all interfaces
  // (0.0.0.0)
  Address sinkLocalAddress(InetSocketAddress(Ipv4Address::GetAny(), port));
  PacketSinkHelper sinkHelper("ns3::TcpSocketFactory", sinkLocalAddress);
  ApplicationContainer sinkApp = sinkHelper.Install(dstNode);

  // Start/End TCP sender and sink at the same time
  sinkApp.Start(Seconds(0.0));
  tcpSender.Start(Seconds(0.0));
  // sinkApp.Stop(Seconds(60.0));
  // tcpSender.Stop(Seconds(60.0));
  Simulator::Stop(Seconds(60.0));

  Simulator::Run();
  Simulator::Destroy();
}

int main(int argc, char* argv[]) {
  std::string configFile;
  CommandLine cmd;
  cmd.AddValue("config", "Path to YAML config file", configFile);
  cmd.Parse(argc, argv);

  LogComponentEnableAll(LOG_LEVEL_INFO);

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