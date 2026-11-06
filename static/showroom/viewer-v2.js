import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const status=document.getElementById('status');
const scene=new THREE.Scene();scene.background=new THREE.Color('#dedbd5');
const camera=new THREE.PerspectiveCamera(62,innerWidth/innerHeight,.08,90);camera.position.set(0,1.7,10);
const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.6));renderer.setSize(innerWidth,innerHeight);
renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.13;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
document.getElementById('mount').append(renderer.domElement);
scene.add(new THREE.HemisphereLight(0xfff5ed,0x84796e,2.3));
const sun=new THREE.DirectionalLight(0xffecd9,2.1);sun.position.set(-4,9,4);
sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-13;sun.shadow.camera.right=13;
sun.shadow.camera.top=16;sun.shadow.camera.bottom=-16;scene.add(sun);
for(const x of [-6,0,6])for(const z of [-8,0,8]){
 const l=new THREE.PointLight(0xffeddd,14,10,2);l.position.set(x,6.5,z);scene.add(l);
}
const modelUrl=new URL('./assets/moli-boutique-v2.glb',import.meta.url).href;
new GLTFLoader().load(modelUrl,g=>{
 scene.add(g.scene);g.scene.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true}});
 status.textContent='Mimari V2 yüklendi · İlk değerlendirme sürümü';
 setTimeout(()=>{status.style.display='none'},3500);
},p=>{if(p.total)status.textContent='3D mimari indiriliyor: %'+Math.round(p.loaded/p.total*100)},e=>{
 console.error('GLB load failed',e);status.textContent='3D model yüklenemedi. Dosyanın oluşturulup yayınlandığını kontrol edin.';
});
const keys=new Set();let yaw=0,pitch=.08,drag=false,px=0,py=0,last=performance.now();
renderer.domElement.addEventListener('pointerdown',e=>{drag=true;px=e.clientX;py=e.clientY;renderer.domElement.setPointerCapture(e.pointerId)});
renderer.domElement.addEventListener('pointerup',()=>drag=false);
renderer.domElement.addEventListener('pointercancel',()=>drag=false);
renderer.domElement.addEventListener('pointermove',e=>{if(!drag)return;yaw-=(e.clientX-px)*.003;pitch=THREE.MathUtils.clamp(pitch-(e.clientY-py)*.0025,-.43,.43);px=e.clientX;py=e.clientY});
addEventListener('keydown',e=>{if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key))e.preventDefault();keys.add(e.key.toLowerCase())});
addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
for(const b of document.querySelectorAll('[data-k]')){b.addEventListener('pointerdown',e=>{keys.add(b.dataset.k);b.setPointerCapture(e.pointerId)});for(const t of ['pointerup','pointercancel','lostpointercapture'])b.addEventListener(t,()=>keys.delete(b.dataset.k))}
function tick(now){requestAnimationFrame(tick);const dt=Math.min((now-last)/1000,.05);last=now;
 camera.rotation.order='YXZ';camera.rotation.y=yaw;camera.rotation.x=pitch;
 const f=Number(keys.has('w')||keys.has('arrowup'))-Number(keys.has('s')||keys.has('arrowdown'));
 const side=Number(keys.has('d')||keys.has('arrowright'))-Number(keys.has('a')||keys.has('arrowleft'));
 const scale=3*dt;camera.position.x=THREE.MathUtils.clamp(camera.position.x+(-Math.sin(yaw)*f+Math.cos(yaw)*side)*scale,-7.8,7.8);
 camera.position.z=THREE.MathUtils.clamp(camera.position.z+(-Math.cos(yaw)*f-Math.sin(yaw)*side)*scale,-11,11);
 renderer.render(scene,camera);
}requestAnimationFrame(tick);
addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)});
