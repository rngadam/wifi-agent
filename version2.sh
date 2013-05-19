echo "convert join"
./convert_from_hash_to_z.py "wifi|join" "wifi|join-by-timestamp"
echo "convert left"
./convert_from_hash_to_z.py "wifi|left" "wifi|left-by-timestamp"
