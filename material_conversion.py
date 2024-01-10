bl_info = {
    "name": "Material Conversion",
    "description": "",
    "author": "Victor Kostin",
    "version": (0, 0, 1),
    "blender": (3, 4, 1),
    "location": "Properties > Materials > Material Conversion",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Development"
}

import bpy
import random as rnd
from typing import Any


from bpy.utils import (register_class, unregister_class)
from bpy.types import (Panel, Operator, Node)

addon_name = __name__
# ------------------------------------------------------------------------
#   operators
# ------------------------------------------------------------------------


class material_conversion(Operator):
    bl_idname = "object.material_conversion"
    bl_label = "Material Conversion"
    bl_options = {'REGISTER', 'UNDO'}

    def __init__(self):
        self.mat_nodes: Any = None
        self.mat_links: Any = None

    @staticmethod
    def replace_material(mesh, old_material, new_material):
        for s in mesh.material_slots:
            if s.material.name == old_material.name:
                s.material = new_material

    def create_node(self, name: str, location: list) -> Node:
        node = self.mat_nodes.new(name)
        node.location = location
        return node

    def view_dot_init(self):
        geometry_node = self.create_node("ShaderNodeNewGeometry", [-2700, 750])
        camera_node = self.create_node("ShaderNodeCameraData", [-2700, 450])

        camera_normal_dot_node = self.create_node("ShaderNodeVectorMath", [-2000, 750])
        camera_normal_dot_node.operation = "DOT_PRODUCT"

        camera_vector_transform_node = self.create_node("ShaderNodeVectorTransform", [-2500, 550])
        camera_vector_transform_node.vector_type = "NORMAL"
        camera_vector_transform_node.convert_from = "CAMERA"
        camera_vector_transform_node.convert_to = "WORLD"

        camera_vector_multiply_node = self.create_node("ShaderNodeVectorMath", [-2250, 550])
        camera_vector_multiply_node.operation = "MULTIPLY"
        camera_vector_multiply_node.inputs[1].default_value = [-1.0, -1.0, -1.0]

        view_normal_dot_inverse_normal = self.create_node("ShaderNodeMath", [-1600, 900])
        view_normal_dot_inverse_normal.operation = "SUBTRACT"
        view_normal_dot_inverse_normal.inputs[0].default_value = 1.0

        dot_contrast_value = self.create_node("ShaderNodeValue", [-1600, 700])
        dot_contrast_value.outputs[0].default_value = 5.4

        dot_power_node = self.create_node("ShaderNodeMath", [-1300, 900])
        dot_power_node.operation = "POWER"

        frame = self.create_node("NodeFrame", [-1600, 600])
        frame.label = "Contrast"

        self.mat_links.new(geometry_node.outputs['Normal'], camera_normal_dot_node.inputs[0])
        self.mat_links.new(camera_node.outputs[0], camera_vector_transform_node.inputs[0])
        self.mat_links.new(camera_vector_transform_node.outputs[0], camera_vector_multiply_node.inputs[0])
        self.mat_links.new(camera_vector_multiply_node.outputs[0], camera_normal_dot_node.inputs[1])
        self.mat_links.new(camera_normal_dot_node.outputs[1], view_normal_dot_inverse_normal.inputs[1])
        self.mat_links.new(view_normal_dot_inverse_normal.outputs[0], dot_power_node.inputs[0])
        self.mat_links.new(dot_contrast_value.outputs[0], dot_power_node.inputs[1])

        return dot_power_node

    def calculate_ior(self) -> Node:
        base_ior_value = self.create_node("ShaderNodeValue", [-2700, 300])
        base_ior_value.outputs[0].default_value = 1.0

        user_ior_value = self.create_node("ShaderNodeValue", [-2700, 200])
        user_ior_value.outputs[0].default_value = 1.5

        subtract_node = self.create_node("ShaderNodeMath", [-2400, 350])
        subtract_node.operation = "SUBTRACT"

        add_node = self.create_node("ShaderNodeMath", [-2400, 200])
        add_node.operation = "ADD"

        divide_node = self.create_node("ShaderNodeMath", [-2200, 300])
        divide_node.operation = "DIVIDE"

        mul_node = self.create_node("ShaderNodeMath", [-2000, 425])
        mul_node.operation = "MULTIPLY"

        frame = self.create_node("NodeFrame", [-2700, 100])
        frame.label = "IOR"

        self.mat_links.new(base_ior_value.outputs[0], subtract_node.inputs[0])
        self.mat_links.new(user_ior_value.outputs[0], subtract_node.inputs[1])

        self.mat_links.new(base_ior_value.outputs[0], add_node.inputs[0])
        self.mat_links.new(user_ior_value.outputs[0], add_node.inputs[1])

        self.mat_links.new(subtract_node.outputs[0], divide_node.inputs[0])
        self.mat_links.new(add_node.outputs[0], divide_node.inputs[1])

        self.mat_links.new(divide_node.outputs[0], mul_node.inputs[0])
        self.mat_links.new(divide_node.outputs[0], mul_node.inputs[1])

        return mul_node

    def direct_dot_init(self) -> Node:
        geometry_node = self.create_node("ShaderNodeNewGeometry", [-1300, 0])

        geometry_transform_node = self.create_node("ShaderNodeVectorTransform", [-1100, 0])
        geometry_transform_node.vector_type = "NORMAL"
        geometry_transform_node.convert_from = "OBJECT"
        geometry_transform_node.convert_to = "WORLD"

        dot_node = self.create_node("ShaderNodeVectorMath", [-900, 100])
        dot_node.operation = "DOT_PRODUCT"
        dot_node.inputs[1].default_value = (0, 0, 1)

        self.mat_links.new(geometry_node.outputs["Normal"], geometry_transform_node.inputs[0])
        self.mat_links.new(geometry_transform_node.outputs[0], dot_node.inputs[0])

        return dot_node

    def execute(self, context):
        active_mat = bpy.context.active_object.active_material
        active_mesh = bpy.context.active_object

        if not active_mat or not active_mesh:
            self.report({'WARNING'}, "Active Object or Active Material not found")
            return{'CANCELLED'}

        mat_name = active_mat.name + "_Conversion"
        mat = bpy.data.materials.new(mat_name)

        mat.use_nodes = True
        self.mat_nodes = mat.node_tree.nodes
        self.mat_links = mat.node_tree.links
        remove_node = self.mat_nodes.get('Principled BSDF')
        if remove_node:
            self.mat_nodes.remove(remove_node)
            

        derived_color = None

        # Search Color and Image
        try:
            surface_node = active_mat.node_tree.nodes.get('Material Output').inputs['Surface'].links[0].from_node
            try:
                image = surface_node.image
                derived_color = self.mat_nodes.new('ShaderNodeTexImage')
                derived_color.image = image
            except:
                print("Surface image not found")
        except:
            self.report({'WARNING'}, "Material Output surface not found")
            return{'CANCELLED'}

        if not derived_color:
            try:
                try:
                    surface_base_color = surface_node.inputs['Base Color']
                except:
                    surface_base_color = surface_node.inputs['Color']
            except:
                self.report({'WARNING'}, "Image and Color not found")
                return {'CANCELLED'}

            try:
                image = surface_base_color.links[0].from_node.image
                derived_color = self.mat_nodes.new('ShaderNodeTexImage')
                derived_color.image = image
            except:
                color1 = surface_base_color.default_value
                derived_color = self.mat_nodes.new('ShaderNodeRGB')
                derived_color.outputs['Color'].default_value = color1

        derived_color.location = (-700, -50)

        # RGB color
        rand_color = (rnd.random(), rnd.random(), rnd.random(), 1)
        rgb_node_new = self.create_node("ShaderNodeRGB", [-700, -250])
        rgb_node_new.outputs['Color'].default_value = rand_color

        mix_shader_node = self.create_node("ShaderNodeMixShader", [-200, 0])
        diffuse_node = self.create_node("ShaderNodeBsdfDiffuse", [-450, -50])
        glossy_node = self.create_node("ShaderNodeBsdfGlossy", [-450, -250])

        # Fresnel part
        view_dot_node = self.view_dot_init()
        ior_value_node = self.calculate_ior()
        direct_dot_node = self.direct_dot_init()

        subtract_node = self.create_node("ShaderNodeMath", [-1600, 550])
        subtract_node.operation = "SUBTRACT"
        subtract_node.inputs[0].default_value = 1.0

        mul_node = self.create_node("ShaderNodeMath", [-1100, 600])
        mul_node.operation = "MULTIPLY"

        add_node = self.create_node("ShaderNodeMath", [-900, 300])
        add_node.operation = "ADD"

        res_mul_node = self.create_node("ShaderNodeMath", [-700, 300])
        res_mul_node.operation = "MULTIPLY"

        map_range_node = self.create_node("ShaderNodeMapRange", [-500, 250])

        self.mat_links.new(ior_value_node.outputs[0], subtract_node.inputs[1])
        self.mat_links.new(view_dot_node.outputs[0], mul_node.inputs[0])
        self.mat_links.new(subtract_node.outputs[0], mul_node.inputs[1])

        self.mat_links.new(mul_node.outputs[0], add_node.inputs[0])
        self.mat_links.new(ior_value_node.outputs[0], add_node.inputs[1])

        self.mat_links.new(add_node.outputs[0], res_mul_node.inputs[0])
        self.mat_links.new(direct_dot_node.outputs[1], res_mul_node.inputs[1])

        self.mat_links.new(res_mul_node.outputs[0], map_range_node.inputs[0])

        self.mat_links.new(derived_color.outputs[0], diffuse_node.inputs[0])
        self.mat_links.new(rgb_node_new.outputs[0], glossy_node.inputs[0])

        self.mat_links.new(map_range_node.outputs[0], mix_shader_node.inputs[0])
        self.mat_links.new(diffuse_node.outputs[0], mix_shader_node.inputs[1])
        self.mat_links.new(glossy_node.outputs[0], mix_shader_node.inputs[2])

        # Output node
        output_node = self.mat_nodes.get('Material Output')
        self.mat_links.new(mix_shader_node.outputs[0], output_node.inputs[0])
        print("All Ok")

        material_conversion.replace_material(active_mesh, active_mat, mat)

        self.report({'INFO'}, "Material is Created")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#   panels
# ------------------------------------------------------------------------


class material_conversion_panel(Panel):
    bl_idname = "MATERIAL_PT_material_conversion_panel"
    bl_label = "Material Conversion"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw(self, context):
        self.layout.operator('object.material_conversion')


classes = (
    material_conversion,
    material_conversion_panel,
)


def register():
    for cls in classes:
        register_class(cls)


def unregister():
    #
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()
