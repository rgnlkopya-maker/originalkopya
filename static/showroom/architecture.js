// Decorative, lightweight architectural layer for the private Moli showroom.
// No database access, no network calls, no paid 3D services.
export function furnishShowroom(THREE, scene, box) {
  const material=(color,roughness=.7,metalness=0)=>new THREE.MeshStandardMaterial({color,roughness,metalness});
  const ivory=material(0xf1ede6), trim=material(0xc4a783,.32,.35);
  const upholstery=material(0x88675c,.91), darkFabric=material(0x514b47,.85);
  const marbleCanvas=document.createElement('canvas');marbleCanvas.width=512;marbleCanvas.height=512;
  const ctx=marbleCanvas.getContext('2d');
  ctx.fillStyle='#e6e1d9';ctx.fillRect(0,0,512,512);
  // Stable, understated marble veins (procedural; not a photographic texture).
  let seed=123456;const rand=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
  for(let n=0;n<23;n++){
    const x=rand()*600-50, y=rand()*600-50;
    ctx.beginPath();ctx.moveTo(x,y);ctx.bezierCurveTo(x+70,y+55,x+130,y-44,x+230,y+86);
    ctx.strokeStyle=n%3===0?'rgba(126,116,111,.19)':'rgba(145,139,132,.10)';
    ctx.lineWidth=.7+rand()*1.6;ctx.stroke();
  }
  const texture=new THREE.CanvasTexture(marbleCanvas);texture.wrapS=texture.wrapT=THREE.RepeatWrapping;
  texture.repeat.set(2,3);texture.colorSpace=THREE.SRGBColorSpace;
  const marble=new THREE.MeshPhysicalMaterial({map:texture,roughness:.29,metalness:0,clearcoat:.32,clearcoatRoughness:.24});
  box(21.75,.018,29.75,marble,0,.012,0,false);
  // Wall skirting and vertical framing.
  for(const side of [-1,1]){
    box(.12,.34,29.5,ivory,side*10.83,.21,0);
    for(const z of [-11,-4,3,10]){
      box(.065,5.2,.08,trim,side*10.75,4.1,z-2.65,false);
      box(.065,5.2,.08,trim,side*10.75,4.1,z+2.65,false);
      box(.065,.06,5.3,trim,side*10.75,6.7,z,false);
      box(.065,.06,5.3,trim,side*10.75,1.5,z,false);
    }
  }
  // Tall entrance arch at the back wall, viewed from the middle aisle.
  const archRadius=1.9,cx=0,archY=4.6,cz=-14.66;
  const archPoints=[];
  for(let i=0;i<=48;i++){const angle=Math.PI-i*Math.PI/48;archPoints.push(new THREE.Vector3(cx+archRadius*Math.cos(angle),archY+archRadius*Math.sin(angle),cz));}
  const archCurve=new THREE.CatmullRomCurve3(archPoints);
  const arch=new THREE.Mesh(new THREE.TubeGeometry(archCurve,64,.115,10,false),ivory);scene.add(arch);
  for(const x of [-archRadius,archRadius])box(.23,4.5,.22,ivory,x,2.35,cz);
  box(4.2,.18,.16,trim,0,.2,cz);
  // Warm wall sconces and recessed display lighting.
  for(const x of [-6.8,6.8]){
    const sconce=box(.14,.58,.22,trim,x,4.75,-14.62,false);
    const glow=new THREE.PointLight(0xffe7c6,6,4,2);glow.position.set(x,4.55,-14.12);scene.add(glow);
    sconce.castShadow=false;
  }
  // Hanging display rods. The existing gown mannequins stand in front of them.
  for(const x of [-8.5,8.5]){
    for(const z of [-8,0,8]){
      box(2.3,.045,.055,trim,x,3.15,z,false);
      for(const offset of [-1.06,1.06])box(.045,.55,.045,trim,x+offset,3.4,z,false);
    }
  }
  // Reception counter on the far right.
  const counter=box(3.7,1.12,1.22,marble,6.7,.56,-12,false);counter.castShadow=true;
  box(3.84,.11,1.36,ivory,6.7,1.17,-12,false);
  box(3.72,.09,.075,trim,6.7,.19,-11.37,false);
  // Lounge corner near the entrance, leaving the central aisle unobstructed.
  const carpet=box(5.4,.035,4.2,material(0xc5bcb2,.96),6.65,.045,8.1,false);
  const sofa=box(3.4,.68,1.1,upholstery,7.35,.45,9.95,false);
  box(3.4,.75,.35,upholstery,7.35,1.06,10.48,false);
  for(const x of [5.93,8.77])box(.3,.67,1.05,upholstery,x,.65,9.95,false);
  for(const x of [6.6,7.8])box(.68,.24,.48,darkFabric,x,.83,10.19,false);
  const tableTop=new THREE.Mesh(new THREE.CylinderGeometry(.95,.95,.09,48),marble);
  tableTop.position.set(6.4,.54,6.72);tableTop.receiveShadow=true;scene.add(tableTop);
  const tableLeg=new THREE.Mesh(new THREE.CylinderGeometry(.13,.2,.5,24),trim);tableLeg.position.set(6.4,.28,6.72);scene.add(tableLeg);
  // Architectural ceiling coves + soft pendant sculpture.
  box(19.3,.07,.08,trim,0,8.48,-13.8,false);
  for(const x of [-9.7,9.7])box(.08,.07,27,trim,x,8.48,0,false);
  const sculptureMaterial=new THREE.MeshPhysicalMaterial({color:0xf8f4ed,roughness:.38,metalness:.02,transparent:true,opacity:.74,side:THREE.DoubleSide});
  for(let strand=0;strand<6;strand++){
    const pts=[];for(let i=0;i<=24;i++){
      const t=i/24*Math.PI*2;
      pts.push(new THREE.Vector3(Math.sin(t*1.1+strand)*(.85+strand*.09),7.5+Math.sin(t*2+strand)*.3-strand*.055,-3.8+Math.cos(t+strand*.68)*1.35));
    }
    const line=new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),40,.025,5,false),sculptureMaterial);
    scene.add(line);
  }
  // Soft targeted illumination of garments, warm rather than overexposed.
  for(const x of [-6.2,6.2])for(const z of [-8,0,8]){
    const light=new THREE.SpotLight(0xffe8cb,9,8,Math.PI/7,.72,1.6);
    light.position.set(x*1.12,7,z);light.target.position.set(x,1.8,z);
    scene.add(light,light.target);
  }
}
