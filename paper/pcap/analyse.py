import matplotlib.pyplot as plt
from scapy.all import rdpcap, TCP
import datetime
import argparse

def analyse_pcap(pcap_file, output_file=None):
    """
    analyse a PCAP file and produce a packet number vs time plot.
    
    Args:
        pcap_file (str): Path to the PCAP file
        output_file (str, optional): Path to save the output graph. If None, displays the graph.
    """
    # Read the PCAP file
    print(f"Reading PCAP file: {pcap_file}")
    packets = rdpcap(pcap_file)
    
    # Extract timestamps
    timestamps = []
    start_time = None
    
    for i, packet in enumerate(packets):
        if not packet.haslayer(TCP):
            continue
        if hasattr(packet, 'time'):
            if start_time is None:
                start_time = packet.time
            # Calculate relative time in seconds
            rel_time = packet.time - start_time
            timestamps.append((i+1, rel_time))
    
    if not timestamps:
        print("No timestamps found in the PCAP file.")
        return
    
    # Create the plot
    plt.figure(figsize=(12, 6))
    packet_nums, times = zip(*timestamps)
    plt.plot(times, packet_nums, marker='.', linestyle='-', markersize=2)
    
    # Add grid and labels
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xlabel('Time (seconds)')
    plt.ylabel('Packets Number')
    plt.title(f'Packet Sequence Diagram - {pcap_file}')
    
    # Add timestamp
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    plt.figtext(0.01, 0.01, f'Generated: {current_time}', fontsize=8)
    
    # Save or display the plot
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {output_file}")
    else:
        plt.tight_layout()
        plt.show()

def main():
    parser = argparse.ArgumentParser(description='Create packet sequence diagrams from PCAP files')
    parser.add_argument('pcap_files', nargs='+', help='PCAP files to analyse')
    parser.add_argument('-o', '--output', help='Output directory for saved plots')
    args = parser.parse_args()
    
    for pcap_file in args.pcap_files:
        if args.output:
            import os
            base_name = os.path.splitext(os.path.basename(pcap_file))[0]
            output_file = os.path.join(args.output, f"{base_name}_sequence.png")
            analyse_pcap(pcap_file, output_file)
        else:
            analyse_pcap(pcap_file)

if __name__ == "__main__":
    main()