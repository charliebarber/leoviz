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

void SetupTCPConfig()
{
    // TCP recovery algorithm
    Config::SetDefault(
        "ns3::TcpL4Protocol::RecoveryType",
        TypeIdValue(TypeId::LookupByName("ns3::TcpClassicRecovery")));
    // Congestion control algorithm
    Config::SetDefault("ns3::TcpL4Protocol::SocketType",
                       StringValue("ns3::TcpLinuxReno"));
    Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue(1073741824));
    Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue(1073741824));
    // Initial congestion window
    Config::SetDefault("ns3::TcpSocket::InitialCwnd", UintegerValue(10));
    // Set delayed ack count
    Config::SetDefault("ns3::TcpSocket::DelAckTimeout", TimeValue(Time("1ms")));
    Config::SetDefault("ns3::TcpSocket::DelAckCount", UintegerValue(1));
    // Set segment size of packet
    Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1024));
    // Enable/disable SACKs (disabled)
    Config::SetDefault("ns3::TcpSocketBase::Sack", BooleanValue(true));
    Config::SetDefault("ns3::TcpSocketBase::MinRto", TimeValue(Seconds(1.0)));
}


void run(YAML::Node shortestConfig, YAML::Node spareConfig, double switchPathsTime, std::string outputDir) {
  NodeContainer nodes;

  // Track how many links created
  int linkCounter = 0;

  Ptr<Node> srcNode;
  Ptr<Node> dstNode;

  // Config::SetDefault("ns3::TcpL4Protocol::SocketType", StringValue("ns3::TcpLinuxReno"));
  // Config::SetDefault(
      // "ns3::TcpL4Protocol::RecoveryType",
      // TypeIdValue(TypeId::LookupByName("ns3::TcpClassicRecovery")));
  SetupTCPConfig();
  // Config::SetDefault("ns3::DropTailQueue<Packet>::MaxSize",
                      //  StringValue("10p"));

  // Read nodes from file and store in above data structures
  auto shortestConfigNodes = shortestConfig["topology"]["nodes"];
  for (size_t i = 0; i < shortestConfigNodes.size(); i++) {
    auto node = shortestConfigNodes[i];
    Ptr<Node> newNode = CreateObject<Node>();
    std::string nodeName = node["name"].as<std::string>();

    // Map Node to Name
    if (!Names::Find<Node>(nodeName)) {
      Names::Add(nodeName, newNode);
    }

    nodes.Add(newNode);

    // First node is the source
    if (i == 0) {
      srcNode = newNode;
    }
    // Last node is the destination
    if (i == shortestConfigNodes.size() - 1) {
      dstNode = newNode;
    }
  }

  // Add all but the first and last nodes as they are already added
  auto spareConfigNodes = spareConfig["topology"]["nodes"];
  for (size_t i = 0; i < spareConfigNodes.size(); i++) {
    auto node = spareConfigNodes[i];
    Ptr<Node> newNode = CreateObject<Node>();
    std::string nodeName = node["name"].as<std::string>();
    NS_LOG_UNCOND("Adding node " << nodeName << " from spare config");

    // Map Node to Name
    if (!Names::Find<Node>(nodeName)) {
      Names::Add(nodeName, newNode);
      nodes.Add(newNode);
    }
  }

  InternetStackHelper internetStack;
  internetStack.Install(nodes);

  Ipv4Address srcAddress;
  Ipv4Address dstAddress;

  std::pair<Ptr<Ipv4>, uint32_t> shortestPathInterface_0;
  std::pair<Ptr<Ipv4>, uint32_t> shortestPathInterface_1;

  // Create links from config
  auto shortestConfigLinks = shortestConfig["topology"]["links"];
  for (size_t i = 0; i < shortestConfigLinks.size(); i++) {
    auto link = shortestConfigLinks[i];
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
    // Hard coded value to be 20Mbps for ISLs (not 20Gbps)
    // p2p.SetDeviceAttribute("DataRate",
                          //  StringValue(link["data_rate"].as<std::string>()));
    p2p.SetDeviceAttribute("DataRate",
                           StringValue("20Mbps"));
    p2p.SetChannelAttribute("Delay",
                            StringValue(link["delay"].as<std::string>()));

    // Install devices for this link
    NetDeviceContainer linkDevices = p2p.Install(linkNodes);

    // Setup IP addresses for this link
    Ipv4AddressHelper ipv4;
    // Generate unique subnet for each link
    std::string subnet = "10.1." + std::to_string(linkCounter++) + ".0";
    ipv4.SetBase(subnet.c_str(), "255.255.255.0");
    Ipv4InterfaceContainer interfaces = ipv4.Assign(linkDevices);

    // Save source and destination IP addresses
    // Only enable PCAPs on these nodes
    // std::string pcapDir = "/home/charlie/fyp/leoviz/networksim/results/";
    std::string pcapDir = outputDir;
    if (i == 0) {
      srcAddress = interfaces.GetAddress(0);
      p2p.EnablePcap(pcapDir + "src_", linkDevices.Get(0));
      // Hard coded to 4Mbps (Not 4Gbps)
      p2p.SetDeviceAttribute("DataRate", StringValue("4Mbps"));
    }
    if (i == 1) {
      shortestPathInterface_0 = interfaces.Get(0);
      shortestPathInterface_1 = interfaces.Get(1);
    }
    if (i == shortestConfigLinks.size() - 1) {
      dstAddress = interfaces.GetAddress(1);
      p2p.EnablePcap(pcapDir + "dst_", linkDevices.Get(1));
      // Hard coded to 4Mbps (Not 4Gbps)
      p2p.SetDeviceAttribute("DataRate", StringValue("4Mbps"));
    }
  }

  NS_LOG_UNCOND("Shortest path links created");
  
  std::pair<Ptr<Ipv4>, uint32_t> sparePathInterface_0;
  std::pair<Ptr<Ipv4>, uint32_t> sparePathInterface_1;

  // Create links from spare config
  auto spareConfigLinks = spareConfig["topology"]["links"];
  for (size_t i = 1; i < spareConfigLinks.size(); i++) {
    auto link = spareConfigLinks[i];
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
    

    // Hard coded value to be 20Mbps for ISLs (not 20Gbps)
    // p2p.SetDeviceAttribute("DataRate",
                          //  StringValue(link["data_rate"].as<std::string>()));
    p2p.SetDeviceAttribute("DataRate",
                           StringValue("20Mbps"));
    p2p.SetChannelAttribute("Delay",
                            StringValue(link["delay"].as<std::string>()));

    // Install devices for this link
    NetDeviceContainer linkDevices = p2p.Install(linkNodes);

    // Setup IP addresses for this link
    Ipv4AddressHelper ipv4;
    // Generate unique subnet for each link
    std::string subnet = "10.1." + std::to_string(linkCounter++) + ".0";
    ipv4.SetBase(subnet.c_str(), "255.255.255.0");
    Ipv4InterfaceContainer interfaces = ipv4.Assign(linkDevices);

    // Capture the point at which the spare path starts
    if (i == 1) {
      sparePathInterface_0 = interfaces.Get(0);
      sparePathInterface_0.first->SetDown(sparePathInterface_0.second);
      sparePathInterface_1 = interfaces.Get(1);
      sparePathInterface_1.first->SetDown(sparePathInterface_1.second);
    }

    // Save source and destination IP addresses
    // Only enable PCAPs on these nodes
    // std::string pcapDir = "/home/charlie/fyp/leoviz/networksim/results/";
    std::string pcapDir = outputDir;
    if (i == spareConfigLinks.size() - 1) {
      // dstAddress = interface.GetAddress(1);
      p2p.EnablePcapAll(pcapDir + "dst_");
      // Hard coded to 4Mbps (Not 4Gbps)
      p2p.SetDeviceAttribute("DataRate", StringValue("4Mbps"));
    }
  }

  NS_LOG_UNCOND("Spare path links created");

  // Setup TCP Experiments
  Ipv4GlobalRoutingHelper::PopulateRoutingTables();
  uint16_t port = 50000;
  // Install TCP sender on source node
  BulkSendHelper bulkSendHelper("ns3::TcpSocketFactory",
                            InetSocketAddress(dstAddress, port));
  bulkSendHelper.SetAttribute("MaxBytes", UintegerValue(1000000000));
  // sendHelper.SetAttribute("SendSize", UintegerValue(1024));
  auto tcpSender = bulkSendHelper.Install(srcNode);

  // Install packet sink on destination node, receiving on all interfaces
  // (0.0.0.0)
  Address sinkLocalAddress(InetSocketAddress(Ipv4Address::GetAny(), port));
  PacketSinkHelper sinkHelper("ns3::TcpSocketFactory", sinkLocalAddress);
  ApplicationContainer sinkApp = sinkHelper.Install(dstNode);

  Ptr<OutputStreamWrapper> routingStream = Create<OutputStreamWrapper>(&std::cout);

  // Add downing of interface at scheduled time
  Simulator::Schedule(Seconds(switchPathsTime), [shortestPathInterface_0, shortestPathInterface_1, sparePathInterface_0, sparePathInterface_1](){
    shortestPathInterface_0.first->SetDown(shortestPathInterface_0.second);
    shortestPathInterface_1.first->SetDown(shortestPathInterface_1.second);
    sparePathInterface_0.first->SetUp(sparePathInterface_0.second);
    sparePathInterface_1.first->SetUp(sparePathInterface_1.second);
    Ipv4GlobalRoutingHelper::RecomputeRoutingTables();
  });

  // Ipv4GlobalRoutingHelper::PrintRoutingTableAllAt(Seconds(0), routingStream);
  // Ipv4GlobalRoutingHelper::PrintRoutingTableAllAt(Seconds(switchPathsTime + 1.0), routingStream);

  // Start/End TCP sender and sink at the same time
  sinkApp.Start(Seconds(0.0));
  tcpSender.Start(Seconds(0.0));
  // sinkApp.Stop(Seconds(60.0));
  tcpSender.Stop(Seconds(600.0));
  Simulator::Stop(Seconds(600.0));

  Simulator::Run();
  Simulator::Destroy();
}

int main(int argc, char* argv[]) {
  std::string shortestConfigFile;
  std::string spareConfigFile;
  std::string outputDir;
  double switchPathsTime;
  CommandLine cmd;
  cmd.AddValue("shortestConfig", "Path to YAML config file", shortestConfigFile);
  cmd.AddValue("spareConfig", "Path to YAML config file", spareConfigFile);
  cmd.AddValue("switchPathsTime", "Time in seconds at which paths are switched", switchPathsTime);
  cmd.AddValue("output-dir", "Output directory", outputDir);
  cmd.Parse(argc, argv);

  
  // LogComponentEnableAll(LOG_LEVEL_ERROR);
  // LogComponentEnableAll(LOG_LEVEL_INFO);
  LogComponentDisableAll(LOG_LEVEL_ALL);
  // ns3::LogComponentEnable("TcpLinuxReno", ns3::LOG_LEVEL_ALL);
  // ns3::LogComponentEnable("TcpLinuxReno", ns3::LOG_PREFIX_TIME);
  // ns3::LogComponentEnable("TcpSocketBase", ns3::LOG_LEVEL_DEBUG);
  // ns3::LogComponentEnable("TcpSocketBase", ns3::LOG_PREFIX_TIME);
  // ns3::LogComponentEnable("TcpL4Protocol", ns3::LOG_LEVEL_DEBUG);
  // ns3::LogComponentEnable("TcpL4Protocol", ns3::LOG_PREFIX_TIME);
  // ns3::LogComponentEnable("TcpTxBuffer", ns3::LOG_LEVEL_INFO);
  // ns3::LogComponentEnable("TcpTxBuffer", ns3::LOG_PREFIX_TIME);

  try {
    auto shortestConfig = ReadYamlConfig(shortestConfigFile);
    auto spareConfig = ReadYamlConfig(spareConfigFile);
    NS_LOG_UNCOND("Successfully read YAML config:");
    run(shortestConfig, spareConfig, switchPathsTime, outputDir);
  } catch (const std::exception& e) {
    NS_LOG_ERROR("Failed to read config: " << e.what());
    return 1;
  }

  return 0;
}