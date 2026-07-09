import os
import urllib.request
import networkx as nx

def main():
    dest_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topologies"))
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, "internetmci.graphml")

    url = "http://www.topology-zoo.org/files/Mci.graphml"
    download_success = False

    print(f"Attempting to download InternetMCI topology from: {url}")
    try:
        urllib.request.urlretrieve(url, dest_path)
        # Verify it can be read by networkx
        G = nx.read_graphml(dest_path)
        print(f"Successfully downloaded MCI topology: {len(G.nodes)} nodes, {len(G.edges)} edges.")
        download_success = True
    except Exception as e:
        print(f"Download failed or invalid: {e}. Generating synthetic InternetMCI topology...")

    if not download_success:
        # Create a synthetic InternetMCI network with 19 nodes and 33 links
        G = nx.DiGraph()
        # Define 19 nodes corresponding to MCI backbone cities
        cities = {
            '0': "Chicago", '1': "Cleveland", '2': "Pittsburgh", '3': "Boston", '4': "New York",
            '5': "Washington", '6': "Atlanta", '7': "Miami", '8': "New Orleans", '9': "Houston",
            '10': "Austin", '11': "Dallas", '12': "Denver", '13': "Salt Lake City", '14': "Phoenix",
            '15': "Los Angeles", '16': "San Francisco", '17': "Seattle", '18': "Minneapolis"
        }
        for node_id, city_name in cities.items():
            G.add_node(node_id, label=city_name, Latitude=0.0, Longitude=0.0)

        # 33 bidirectional-like links (or 33 directed links)
        # Let's specify 33 directed links to match the graph density of 19 nodes, 33 links.
        # We will design a realistic backbone topology.
        edges = [
            ('17', '16'), ('17', '18'), ('17', '13'), # Seattle to SF, Minneapolis, Salt Lake City
            ('16', '15'), ('16', '13'),                # SF to LA, Salt Lake City
            ('15', '14'), ('15', '13'),                # LA to Phoenix, Salt Lake City
            ('14', '11'), ('14', '12'),                # Phoenix to Dallas, Denver
            ('13', '12'), ('13', '18'),                # Salt Lake City to Denver, Minneapolis
            ('12', '11'), ('12', '0'),                 # Denver to Dallas, Chicago
            ('18', '0'),                               # Minneapolis to Chicago
            ('11', '10'), ('11', '9'),                 # Dallas to Austin, Houston
            ('10', '9'),                               # Austin to Houston
            ('8', '6'),                                # New Orleans to Atlanta
            ('0', '8'),                                # Chicago to New Orleans (Allowed Core->FIN)
            ('6', '5'),                                # Atlanta to Washington
            ('7', '5'),                                # Miami to Washington
            ('5', '2'), ('5', '4'),                    # Washington to Pittsburgh, NY
            ('2', '1'), ('2', '0'),                    # Pittsburgh to Cleveland, Chicago
            ('1', '0'), ('1', '4'),                    # Cleveland to Chicago, NY
            ('4', '3'),                                # NY to Boston
            ('3', '0'),                                # Boston to Chicago
            ('0', '6'),                                # Chicago to Atlanta
            ('15', '11'),                              # LA to Dallas
            ('0', '7'),                                # Chicago to Miami (Allowed Core->FIN)
            ('14', '8')                                # Phoenix to New Orleans (Allowed IT->FIN)
        ]
        # Check: we need exactly 33 links
        assert len(edges) == 33, f"Need 33 edges, got {len(edges)}"
        
        for u, v in edges:
            G.add_edge(u, v)

        nx.write_graphml(G, dest_path)
        print(f"Successfully generated synthetic InternetMCI topology at: {dest_path}")
        print(f"Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")

if __name__ == "__main__":
    main()
