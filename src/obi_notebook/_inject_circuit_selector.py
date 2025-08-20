import os
import time
from datetime import datetime
from bluepysnap import Circuit
from entitysdk import Client, models
from obi_notebook import get_entities

client = Client(environment="production", project_context=project_context, token_manager=token)
circuit_ids = []
circuit_ids = get_entities.get_entities("circuit", token, circuit_ids,
                                        project_context=project_context,
                                        multi_select=False, exclude_scales=["single"],
                                        show_pages=True, page_size=12,
                                        default_scale="small", add_columns=["subject.name"])


# Fetch circuit
fetched = client.get_entity(entity_id=circuit_ids[0], entity_type=models.Circuit)
print(f"Circuit fetched: {fetched.name} (ID {fetched.id})\n")
print(f"#Neurons: {fetched.number_neurons}, #Synapses: {fetched.number_synapses}, #Connections: {fetched.number_connections}\n")
print(f"{fetched.description}\n")

# Download SONATA circuit files
asset = [asset for asset in fetched.assets if asset.label=="sonata_circuit"][0]
asset_dir = asset.path 
circuit_dir = "analysis_circuit_" + datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')

t0 = time.time()
client.download_directory(
    entity_id=fetched.id,
    entity_type=models.Circuit,
    asset_id=asset.id,
    output_path=circuit_dir,
    max_concurrent=4,  # Parallel file download
)
t = time.time() - t0
print(f"Circuit files downloaded to '{os.path.join(circuit_dir, asset_dir)}' in {t:.1f}s")


# Path to existing circuit config
circuit_config = os.path.join(circuit_dir, asset_dir, "circuit_config.json")

assert os.path.exists(circuit_config), f"ERROR: Circuit config '{os.path.split(circuit_config)[1]}' not found!"
$CIRC = Circuit(circuit_config)
