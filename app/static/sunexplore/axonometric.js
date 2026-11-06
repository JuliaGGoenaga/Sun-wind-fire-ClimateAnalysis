const THREE = window.THREE;
const OrbitControls = THREE.OrbitControls;
const container = document.getElementById("shade-axonometric");
const scene = new THREE.Scene();
scene.background = new THREE.Color("#f7faf8");

const camera = new THREE.OrthographicCamera(-4.2, 4.2, 3.3, -3.3, 0.1, 80);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "low-power" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.setClearColor("#f7faf8");
renderer.domElement.setAttribute("aria-hidden", "true");
container.replaceChildren(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.minDistance = 3;
controls.maxDistance = 32;
controls.minPolarAngle = 0.06;
controls.maxPolarAngle = Math.PI - 0.06;
controls.target.set(0, 0, 0);

const model = new THREE.Group();
scene.add(model);
scene.add(new THREE.HemisphereLight(0xffffff, 0x82958c, 0.42));

const keyLight = new THREE.DirectionalLight(0xffffff, 0.72);
keyLight.position.set(-5, 8, 7);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(1024, 1024);
scene.add(keyLight);

const fillLight = new THREE.DirectionalLight(0xffffff, 0.14);
fillLight.position.set(5, 3, -4);
scene.add(fillLight);

const materials = {
  wall: new THREE.MeshStandardMaterial({ color: 0xb9c9c2, roughness: 0.88 }),
  reveal: new THREE.MeshStandardMaterial({ color: 0xcbd7d2, roughness: 0.9 }),
  trim: new THREE.MeshStandardMaterial({ color: 0x547b78, roughness: 0.62 }),
  glass: new THREE.MeshPhysicalMaterial({ color: 0x73aaa5, roughness: 0.24, metalness: 0.02, transmission: 0.12 }),
  mullion: new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.5 }),
  horizontal: new THREE.MeshStandardMaterial({ color: 0xcfed70, roughness: 0.58 }),
  vertical: new THREE.MeshStandardMaterial({ color: 0x94b63a, roughness: 0.58 }),
  ground: new THREE.MeshStandardMaterial({ color: 0xd0dbd5, roughness: 0.95 })
};

const addBox = (width, height, depth, x, y, z, material, castsShadow = true) => {
  if (width <= 0 || height <= 0 || depth <= 0) return;
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
  mesh.position.set(x, y, z);
  mesh.castShadow = castsShadow;
  mesh.receiveShadow = true;
  model.add(mesh);
  return mesh;
};

const clearModel = () => {
  while (model.children.length) {
    const child = model.children.pop();
    child.geometry.dispose();
  }
};

const resetView = () => {
  camera.position.set(7, 7, 7);
  camera.up.set(0, 1, 0);
  camera.zoom = 1;
  camera.updateProjectionMatrix();
  controls.target.set(0, 0, 0);
  controls.update();
};

const update = ({ width, height, horizontalEnabled, horizontalLength, verticalEnabled, verticalLength, verticalSide }) => {
  clearModel();

  const wallWidth = Math.max(width + 1, 3.8);
  const wallHeight = Math.max(height + 1, 3.2);
  const wallDepth = 0.25;
  const sideMargin = (wallWidth - width) / 2;
  const verticalMargin = (wallHeight - height) / 2;
  const windowBottom = -wallHeight / 2 + verticalMargin;
  const windowTop = windowBottom + height;
  const windowLeft = -width / 2;
  const windowRight = width / 2;
  const wallFront = wallDepth / 2;

  addBox(sideMargin, wallHeight, wallDepth, -wallWidth / 2 + sideMargin / 2, 0, 0, materials.wall);
  addBox(sideMargin, wallHeight, wallDepth, wallWidth / 2 - sideMargin / 2, 0, 0, materials.wall);
  addBox(width, verticalMargin, wallDepth, 0, -wallHeight / 2 + verticalMargin / 2, 0, materials.wall);
  addBox(width, verticalMargin, wallDepth, 0, wallHeight / 2 - verticalMargin / 2, 0, materials.wall);

  const frame = 0.055;
  const openingHeight = height - frame * 2;
  const openingWidth = width - frame * 2;
  const glassZ = -wallFront + 0.035;
  addBox(openingWidth, openingHeight, 0.025, 0, (windowBottom + windowTop) / 2, glassZ, materials.glass, false);

  const frameZ = wallFront + frame / 2;
  addBox(frame, height, frame, windowLeft + frame / 2, (windowBottom + windowTop) / 2, frameZ, materials.trim);
  addBox(frame, height, frame, windowRight - frame / 2, (windowBottom + windowTop) / 2, frameZ, materials.trim);
  addBox(width, frame, frame, 0, windowTop - frame / 2, frameZ, materials.trim);
  addBox(width, frame, frame, 0, windowBottom + frame / 2, frameZ, materials.trim);

  addBox(frame * 0.55, openingHeight, 0.025, 0, (windowBottom + windowTop) / 2, glassZ + 0.018, materials.mullion, false);
  addBox(openingWidth, frame * 0.55, 0.025, 0, (windowBottom + windowTop) / 2, glassZ + 0.02, materials.mullion, false);

  if (horizontalEnabled && horizontalLength > 0) {
    const projection = horizontalLength + wallFront;
    const slabThickness = 0.08;
    addBox(width + 0.24, slabThickness, projection, 0, windowTop + slabThickness / 2, projection / 2, materials.horizontal);
  }

  if (verticalEnabled && verticalLength > 0) {
    const finThickness = 0.07;
    const finHeight = Math.max(height - 0.04, 0.05);
    const finX = verticalSide === "left" ? windowLeft + finThickness / 2 : windowRight - finThickness / 2;
    const projection = verticalLength + wallFront;
    addBox(finThickness, finHeight, projection, finX, windowBottom + finHeight / 2, projection / 2, materials.vertical);
  }

  const groundDepth = Math.max(horizontalEnabled ? horizontalLength : 0, verticalEnabled ? verticalLength : 0, 0.45) + wallDepth;
  addBox(wallWidth + 0.42, 0.06, groundDepth + 0.36, 0, -wallHeight / 2 - 0.035, groundDepth / 2 - wallFront, materials.ground, false);
};

const resize = () => {
  const { width, height } = container.getBoundingClientRect();
  if (!width || !height) return;
  renderer.setSize(width, height, false);
  const aspect = width / height;
  const viewHeight = 6.8;
  camera.left = -viewHeight * aspect / 2;
  camera.right = viewHeight * aspect / 2;
  camera.top = viewHeight / 2;
  camera.bottom = -viewHeight / 2;
  camera.updateProjectionMatrix();
};

const resizeObserver = new ResizeObserver(resize);
resizeObserver.observe(container);
window.addEventListener("resize", resize);
document.getElementById("reset-axon-view").addEventListener("click", resetView);

resetView();
resize();
window.sunShade3d = { update, resetView };
window.dispatchEvent(new Event("sunshade3dready"));

const animate = () => {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
};
animate();