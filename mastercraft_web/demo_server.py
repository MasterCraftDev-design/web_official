from flask import Flask, request, jsonify, render_template, send_file
import os
import struct
import re
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['IMAGE_FOLDER'] = 'static/images'

# Ensure folders exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['IMAGE_FOLDER']):
    os.makedirs(app.config['IMAGE_FOLDER'])

# Materials class
class materialsFor3DPrinting:
    def __init__(self):
        self.materials_dict = {
            1: {'name': 'ABS', 'mass': 1.04},
            2: {'name': 'PLA', 'mass': 1.25},
            3: {'name': '3k CFRP', 'mass': 1.79},
            4: {'name': 'Plexiglass', 'mass': 1.18},
            5: {'name': 'Alumide', 'mass': 1.36},
            6: {'name': 'Aluminum', 'mass': 2.68},
            7: {'name': 'Brass', 'mass': 8.6},
            8: {'name': 'Bronze', 'mass': 9.0},
            9: {'name': 'Copper', 'mass': 9.0},
            10: {'name': 'Gold_14K', 'mass': 13.6},
            11: {'name': 'Gold_18K', 'mass': 15.6},
            12: {'name': 'Polyamide_MJF', 'mass': 1.01},
            13: {'name': 'Polyamide_SLS', 'mass': 0.95},
            14: {'name': 'Rubber', 'mass': 1.2},
            15: {'name': 'Silver', 'mass': 10.26},
            16: {'name': 'Steel', 'mass': 7.86},
            17: {'name': 'Titanium', 'mass': 4.41},
            18: {'name': 'Resin', 'mass': 1.2}
        }
        
    def get_material_mass(self, material_identifier):
        if isinstance(material_identifier, int) and material_identifier in self.materials_dict:
            return self.materials_dict[material_identifier]['mass']
        else:
            raise ValueError(f"Invalid material identifier: {material_identifier}")

# STL file processing class
class STLUtils:
    def __init__(self):
        self.triangles = []

    def is_binary(self, file):
        with open(file, 'rb') as f:
            header = f.read(80).decode(errors='replace')
            return not header.startswith('solid')

    def read_triangle(self, f):
        struct.unpack("<3f", f.read(12))  # Skip normal
        p1 = struct.unpack("<3f", f.read(12))
        p2 = struct.unpack("<3f", f.read(12))
        p3 = struct.unpack("<3f", f.read(12))
        f.read(2)  # Skip attribute byte count
        return (p1, p2, p3)

    def read_stl(self, file):
        if self.is_binary(file):
            with open(file, "rb") as f:
                f.seek(80)
                length = struct.unpack("@I", f.read(4))[0]
                for _ in range(length):
                    self.triangles.append(self.read_triangle(f))

    def signed_volume_of_triangle(self, p1, p2, p3):
        v321 = p3[0] * p2[1] * p1[2]
        v231 = p2[0] * p3[1] * p1[2]
        v312 = p3[0] * p1[1] * p2[2]
        v132 = p1[0] * p3[1] * p2[2]
        v213 = p2[0] * p1[1] * p3[2]
        v123 = p1[0] * p2[1] * p3[2]
        return (1.0 / 6.0) * (-v321 + v231 + v312 - v132 - v213 + v123)

    def calculate_volume(self, material_mass):
        total_volume = sum(self.signed_volume_of_triangle(p1, p2, p3) for p1, p2, p3 in self.triangles) / 1000  # Volume in cm^3
        total_mass = total_volume * material_mass
        return total_volume, total_mass

    def plot_stl(self, file_name):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Extract the points
        faces = np.array(self.triangles)
        ax.add_collection3d(Poly3DCollection(faces, edgecolor='k'))

        # Auto scaling
        scale = faces.flatten()
        ax.auto_scale_xyz(scale, scale, scale)

        plt.title('STL Preview')
        img_path = os.path.join(app.config['IMAGE_FOLDER'], f"{file_name}.png")
        plt.savefig(img_path)
        plt.close()
        return img_path

# Route to serve the HTML file
@app.route('/')
def upload_file():
    return render_template('upload_stl.html')

# API endpoint for handling file upload, material selection, and generating STL image
@app.route('/calculate', methods=['POST'])
def calculate_mass_and_volume():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    material_id = request.form.get('material_id', type=int, default=2)  # Default to PLA (material_id=2)

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Save the file temporarily
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # Process the file with STLUtils
    stl_utils = STLUtils()
    stl_utils.read_stl(file_path)

    # Get the material's mass
    materials = materialsFor3DPrinting()
    try:
        material_mass = materials.get_material_mass(material_id)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # Calculate the volume and mass
    total_volume, total_mass = stl_utils.calculate_volume(material_mass)

    # Generate an image of the STL file
    image_path = stl_utils.plot_stl(file.filename.split('.')[0])

    # Remove the saved file after processing
    os.remove(file_path)

    # Return the result as JSON
    return jsonify({
        'material_id': material_id,
        'total_volume_cm3': total_volume,
        'total_mass_g': total_mass,
        'image_url': image_path
    })

if __name__ == '__main__':
    app.run(debug=True)
