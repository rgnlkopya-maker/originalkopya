import * as THREE from 'three';
const loading=document.getElementById('loading'),loadingText=document.getElementById('loading-text');
try {
const scene=new THREE.Scene();scene.background=new THREE.Color(0xd9d6d0);scene.fog=new THREE.Fog(0xd9d6d0,25,50);
const camera=new THREE.PerspectiveCamera(65,innerWidth/innerHeight,.08,100);camera.position.set(0,1.7,9);
const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.8));renderer.setSize(innerWidth,innerHeight);
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=0.96;
renderer.outputColorSpace=THREE.SRGBColorSpace;
document.getElementById('stage').appendChild(renderer.domElement);
const mat=(c,rough=.78,metal=0)=>new THREE.MeshStandardMaterial({color:c,roughness:rough,metalness:metal,side:THREE.DoubleSide});
const plaster=mat(0xe5e1da),floorMat=mat(0xbcb5ab,.58),gold=mat(0xa58a60,.35,.42),stone=mat(0xd4cec4,.6),dark=mat(0x393530,.4);
function box(w,h,d,m,x,y,z,shadows=true){const a=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),m);a.position.set(x,y,z);a.receiveShadow=shadows;a.castShadow=shadows;scene.add(a);return a}
box(22,.2,30,floorMat,0,-.12,0);box(22,9,.25,plaster,0,4.4,-15);box(.25,9,30,plaster,-11,4.4,0);box(.25,9,30,plaster,11,4.4,0);
box(22,.2,30,plaster,0,8.8,0);box(22,.22,.18,gold,0,.12,-14.8);
for(let z=-12;z<13;z+=4){box(.075,.015,21,mat(0xc8c0b3,.4),0,.005,z,false)}
for(let z=-10;z<=10;z+=8){for(let x of [-7,0,7]){const light=new THREE.RectAreaLight(0xfff5e8,3.5,5,2);light.position.set(x,8.58,z);light.lookAt(x,0,z);scene.add(light);box(5,.04,2,mat(0xe9e5df,.6),x,8.59,z,false)}}
scene.add(new THREE.HemisphereLight(0xfff6ea,0x8c8176,1.25));
const key=new THREE.DirectionalLight(0xfff1df,1.8);key.position.set(-4,8,6);key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-15;key.shadow.camera.right=15;key.shadow.camera.top=16;key.shadow.camera.bottom=-16;key.shadow.bias=-.0003;scene.add(key);
function frame(x,z){box(3.15,5.2,.09,stone,x,4.1,z);box(3.05,.035,.12,gold,x,1.5,z+.09);box(3.05,.035,.12,gold,x,6.7,z+.09)}
frame(0,-14.72);
const labelMat=mat(0x81786a);
const styles=[
{code:'HL-001',name:'Helen / Şampanya',type:'helen',color:0xf4e4ce,desc:'Yumuşak dökümlü, zarif Helen silüeti.'},
{code:'HL-002',name:'Helen / Kırık Beyaz',type:'helen',color:0xf4eee4,desc:'Akıcı etek yapısı ve sade üst beden.'},
{code:'HL-003',name:'Helen / Pudra',type:'helen',color:0xe6c6bc,desc:'Romantik, hafif ve modern Helen formu.'},
{code:'BL-001',name:'Balık / İnci',type:'balik',color:0xe7e3df,desc:'Vücudu takip eden ve etekte genişleyen balık formu.'},
{code:'BL-002',name:'Balık / Kum',type:'balik',color:0xcdb7a3,desc:'Heykelsi hatları vurgulayan modern balık kesim.'},
{code:'BL-003',name:'Balık / Sedef',type:'balik',color:0xe6d8d1,desc:'Dengeli kuyruk ve rafine balık silüeti.'}
];
const clickable=[];
function gown(item,x,z,rot){const group=new THREE.Group();group.position.set(x,0,z);group.rotation.y=rot;scene.add(group);group.userData=item;
 const fabric=new THREE.MeshPhysicalMaterial({color:item.color,roughness:.72,metalness:0,clearcoat:.12,side:THREE.DoubleSide});
 const pedestal=new THREE.Mesh(new THREE.CylinderGeometry(1.42,1.42,.15,64),stone);pedestal.position.y=.08;pedestal.receiveShadow=true;group.add(pedestal);
 const pole=new THREE.Mesh(new THREE.CylinderGeometry(.018,.018,1.45,12),dark);pole.position.y=1.22;group.add(pole);
 const bodice=new THREE.Mesh(new THREE.CylinderGeometry(.27,.38,.66,32,1),fabric);bodice.position.y=2.03;bodice.scale.z=.72;group.add(bodice);
 const waist=new THREE.Mesh(new THREE.CylinderGeometry(.35,.35,.1,32),fabric);waist.position.y=1.68;group.add(waist);
 const hem=item.type==='helen'?1.16:1.03;
 const profile=item.type==='helen'?[.34,.43,.62,.85,hem]:[.34,.4,.39,.57,hem];
 const levels=[1.66,1.35,.99,.55,.18];const verts=[],indices=[];
 const sides=64;
 for(let i=0;i<levels.length;i++)for(let k=0;k<=sides;k++){let theta=2*Math.PI*k/sides,fold=1+.025*Math.cos(theta*12+i*.4);verts.push(Math.cos(theta)*profile[i]*fold,levels[i]+.018*Math.sin(theta*12),Math.sin(theta)*profile[i]*fold*.79);}
 for(let i=0;i<levels.length-1;i++)for(let k=0;k<sides;k++){let a=i*(sides+1)+k,b=a+sides+1;indices.push(a,b,a+1,b,b+1,a+1)}
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));geo.setIndex(indices);geo.computeVertexNormals();
 const skirt=new THREE.Mesh(geo,fabric);skirt.castShadow=true;group.add(skirt);
 const bust=new THREE.Mesh(new THREE.SphereGeometry(.34,24,12),fabric);bust.position.y=2.32;bust.scale.set(1,.33,.72);group.add(bust);
 for(const sign of [-1,1]){const strap=new THREE.Mesh(new THREE.BoxGeometry(.07,.42,.10),fabric);strap.position.set(sign*.25,2.49,0);strap.rotation.z=sign*.24;group.add(strap)}
 const plaque=new THREE.Mesh(new THREE.BoxGeometry(1.45,.14,.06),gold);plaque.position.set(0,.23,1.11);group.add(plaque);
 const hit=new THREE.Mesh(new THREE.CylinderGeometry(.75,1.25,2.5,24),new THREE.MeshBasicMaterial({visible:false}));hit.position.y=1.42;hit.userData=item;group.add(hit);clickable.push(hit);
}
const positions=[[-6.4,-8,Math.PI/5],[-6.4,0,Math.PI/2.7],[-6.4,8,Math.PI/2.5],[6.4,-8,-Math.PI/5],[6.4,0,-Math.PI/2.7],[6.4,8,-Math.PI/2.5]];
styles.forEach((s,i)=>gown(s,...positions[i]));
// Wall niches and ambient architectural details
for(const side of [-1,1])for(const z of [-8,0,8]){box(.12,4,2.85,mat(0xd3cec7),side*10.78,3,z);box(.14,.08,2.86,gold,side*10.65,5,z)}
const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();
let yaw=0,pitch=0,drag=false,lastX=0,lastY=0,moved=0;const keys=new Set();
function point(ev){const r=renderer.domElement.getBoundingClientRect();pointer.set((ev.clientX-r.left)/r.width*2-1,-(ev.clientY-r.top)/r.height*2+1)}
renderer.domElement.addEventListener('pointerdown',e=>{drag=true;lastX=e.clientX;lastY=e.clientY;moved=0;renderer.domElement.setPointerCapture(e.pointerId)});
renderer.domElement.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-lastX,dy=e.clientY-lastY;moved+=Math.abs(dx)+Math.abs(dy);yaw-=dx*.0032;pitch=Math.max(-.48,Math.min(.48,pitch-dy*.0025));lastX=e.clientX;lastY=e.clientY});
renderer.domElement.addEventListener('pointerup',e=>{drag=false;if(moved>8)return;point(e);ray.setFromCamera(pointer,camera);const hit=ray.intersectObjects(clickable,false)[0];if(hit){const it=hit.object.userData;document.getElementById('item-code').textContent=it.code+' · ÖRNEK MODEL';document.getElementById('item-name').textContent=it.name;document.getElementById('item-desc').textContent=it.desc;document.getElementById('item-variants').textContent='Renk: Görseldeki ton · Beden: Sonradan eklenecek';document.getElementById('details').classList.add('open')}});
document.getElementById('close-details').onclick=()=>document.getElementById('details').classList.remove('open');
addEventListener('keydown',e=>{if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',' '].includes(e.key))e.preventDefault();keys.add(e.key.toLowerCase())});
addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
for(const b of document.querySelectorAll('[data-move]')){const k={forward:'w',backward:'s',left:'a',right:'d'}[b.dataset.move];b.addEventListener('pointerdown',e=>{e.preventDefault();keys.add(k);b.setPointerCapture(e.pointerId)});for(const ev of ['pointerup','pointercancel','lostpointercapture'])b.addEventListener(ev,()=>keys.delete(k))}
let prev=performance.now();
function tick(now){requestAnimationFrame(tick);const dt=Math.min((now-prev)/1000,.05);prev=now;camera.rotation.order='YXZ';camera.rotation.y=yaw;camera.rotation.x=pitch;
 const forward=Number(keys.has('w')||keys.has('arrowup'))-Number(keys.has('s')||keys.has('arrowdown')),strafe=Number(keys.has('d')||keys.has('arrowright'))-Number(keys.has('a')||keys.has('arrowleft'));const speed=3.0*dt;
 const dx=(Math.sin(yaw)*-forward+Math.cos(yaw)*strafe)*speed,dz=(-Math.cos(yaw)*forward-Math.sin(yaw)*strafe)*speed;
 camera.position.x=THREE.MathUtils.clamp(camera.position.x+dx,-8.8,8.8);camera.position.z=THREE.MathUtils.clamp(camera.position.z+dz,-12.7,12.7);
 renderer.render(scene,camera)}
addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)});
requestAnimationFrame(tick);loading.remove();
} catch(err){console.error('Showroom startup failed',err);loadingText.textContent='3D sahne başlatılamadı. Tarayıcınızda WebGL desteğini kontrol edin. Hata: '+err.message;const b=document.createElement('button');b.textContent='Tekrar dene';b.onclick=()=>location.reload();loading.appendChild(b)}
