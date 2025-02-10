# Unpack ns-3
echo "Unpacking NS3 tar"
tar -xjf ns-allinone-3.43.tar.bz2 ns-allinone-3.43/

# Keep only the ns-3.43 subfolder
mv ns-allinone-3.43/ns-3.43/ .
rm -rf ns-allinone-3.43

# Build ns-3
echo "Configuring and building NS3"
cd ns-3.43
./ns3 configure --enable-mpi
./ns3