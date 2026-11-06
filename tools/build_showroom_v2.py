"""Build an editable 3D boutique with Blender and export a single GLB."""
import bpy, math, os, random
from mathutils import Matrix
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
OUT='static/showroom/assets/moli-boutique-v2.glb'
os.makedirs(os.path.dirname(OUT),exist_ok=True)
def mat(name,color,rough=.65,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF')
 bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal
 return m
ivory=mat('Limestone plaster',(.84,.81,.76));white=mat('Ivory lacquer',(.93,.9,.84),.38)
brass=mat('Brushed champagne brass',(.55,.38,.18),.3,.72)
rose=mat('Muted rose upholstery',(.45,.28,.26),.9)
taupe=mat('Warm taupe cushions',(.34,.29,.27),.9)
shadow=mat('Arch recess',(.30,.29,.28))
glass=mat('Frosted chandelier ribbons',(.9,.91,.87),.27)
# Marble is a genuine image texture embedded into glTF (unlike non-exportable shader noise).
N=256;img=bpy.data.images.new('Calacatta marble image',width=N,height=N,alpha=True)
random.seed(28);phase=[random.random()*7 for _ in range(6)]
px=[]
for y in range(N):
 for x in range(N):
  u=x/N;v=y/N
  h=.018*math.sin(u*13+v*24)
  vein=sum(math.exp(-((math.sin((u*.9+v*.6)*20+p+math.sin(v*9+p))-.96)/.07)**2)*.032 for p in phase)
  c=.91+h-vein;px.extend([c,c-.016,c-.044,1])
img.pixels.foreach_set(px);img.pack()
marble=mat('Polished marble PBR',(.9,.88,.85),.24)
node=marble.node_tree.nodes.new('ShaderNodeTexImage');node.image=img
marble.node_tree.links.new(node.outputs['Color'],marble.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
def cube(name,pos,dims,m,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos)
 o=bpy.context.object;o.name=name;o.dimensions=dims
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:
  b=o.modifiers.new('Soft edges','BEVEL');b.width=bevel;b.segments=3
  o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 o.data.materials.append(m);return o
def cyl(name,pos,r,d,m):
 bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=r,depth=d,location=pos)
 o=bpy.context.object;o.name=name;o.data.materials.append(m)
 # cylinders are Z-axis in Blender, design is Y-up
 o.rotation_euler[0]=math.pi/2
 return o
def tube(name,pts,m,r=.025):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=r;c.bevel_resolution=3
 s=c.splines.new('POLY');s.points.add(len(pts)-1)
 for point,xyz in zip(s.points,pts):point.co=(*xyz,1)
 o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);o.data.materials.append(m)
cube('Real textured Calacatta marble floor',(0,-.07,0),(18,.14,25),marble,.012)
cube('Left wall',(-9,3.5,0),(.18,7,25),ivory,.03)
cube('Right wall',(9,3.5,0),(.18,7,25),ivory,.03)
cube('Rear wall',(0,3.5,-12.5),(18,7,.18),ivory,.03)
cube('Warm white ceiling',(0,7.04,0),(18,.12,25),white,.025)
for side in [-1,1]:
 cube('Cove lighting trim',(side*8.4,6.86,0),(.07,.07,24),brass,.016)
 cube('Ivory skirting',(side*8.85,.15,0),(.14,.3,24),white,.025)
 for z in [-9,-3,3,9]:
  cube('Wall panel inset',(side*8.88,3.4,z),(.03,4.2,4.75),white,.03)
  for q in [-2.3,2.3]:
   cube('Panel border',(side*8.84,3.4,z+q),(.07,4.3,.06),brass,.01)
  for y in [1.25,5.55]:
   cube('Panel molding',(side*8.84,y,z),(.07,.06,4.65),brass,.01)
  railx=side*7
  cube('Brass dress rail',(railx,3.03,z),(.05,.05,3),brass,.012)
  for q in [-1.43,1.43]:cube('Rail bracket',(railx,3.3,z+q),(.045,.6,.045),brass,.008)
# Real semicircle arch trim and a darker, inset alcove
cube('Recess backdrop',(0,3.4,-12.32),(3.4,5,.06),shadow,.01)
for x in [-1.78,1.78]:cube('Arch column',(x,2.3,-12.1),(.22,4.6,.22),white,.07)
arc=[(1.78*math.cos(math.pi*i/64),4.6+1.78*math.sin(math.pi*i/64),-12.1) for i in range(65)]
tube('Curved architectural arch',arc,white,.125)
cube('Arch marble threshold',(0,.11,-11.75),(4,.22,1.5),marble,.035)
# Counter with fluted brass frontage
cube('Reception counter',(5.7,.55,-10.55),(3.4,1.1,1.15),white,.08)
cube('Reception marble slab',(5.7,1.14,-10.55),(3.6,.12,1.32),marble,.05)
for i in range(13):cube('Fluted counter brass',(4.2+i*.245,.52,-9.96),(.032,.8,.06),brass,.009)
# Lounge, sofa, table and rug
rug=mat('Natural wool rug',(.65,.60,.55),.97)
cube('Lounge area rug',(5.5,.03,8),(5.4,.04,4.4),rug,.08)
cube('Rose sofa seat',(6,.43,9.7),(3.65,.65,1.2),rose,.15)
cube('Sofa back',(6,1.03,10.25),(3.65,.8,.35),rose,.12)
for x in [4.4,7.6]:cube('Sofa arm',(x,.7,9.65),(.36,.7,1.3),rose,.12)
for x in [5.3,6.6]:cube('Taupe cushion',(x,1.03,10),(.55,.4,.19),taupe,.09)
cyl('Round marble table',(5.3,.55,6.6),.88,.11,marble)
cyl('Brass coffee table base',(5.3,.28,6.6),.16,.48,brass)
# Track spot housings and chandelier
for x in [-5,0,5]:
 for z in [-8,0,8]:cyl('Ceiling downlight',(x,6.88,z),.14,.10,white)
for n in range(6):
 pts=[(math.sin(t+n*.8)*1.1,6.2+math.sin(t*2+n)*.24,-2+math.cos(t+n*.75)*1.25) for t in [2*math.pi*i/70 for i in range(71)]]
 tube('Hanging sculptural light',pts,glass,.028)
# Change native Y-up modeling coordinates into Blender's Z-up before glTF exporter
rot=Matrix.Rotation(math.pi/2,4,'X')
for obj in bpy.context.scene.objects:obj.matrix_world=rot @ obj.matrix_world
bpy.ops.export_scene.gltf(filepath=OUT,export_format='GLB',export_apply=True,export_yup=True)
print('MOLI_V2_GLB_OK',os.path.getsize(OUT))
