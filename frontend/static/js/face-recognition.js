// face-recognition.js
// Face recognition module using face-api.js

let faceApiLoaded = false;
let modelsLoaded = false;

// Load face-api.js models
async function loadFaceApiModels() {
  if (modelsLoaded) return true;
  
  try {
    console.log('Loading face-api.js models...');
    
    const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model';
    
    await Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
      faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
      faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
    ]);
    
    modelsLoaded = true;
    console.log('Face-api.js models loaded successfully');
    return true;
  } catch (error) {
    console.error('Error loading face-api.js models:', error);
    return false;
  }
}

// Detect face and get descriptor from image
async function detectFaceAndGetDescriptor(imageElement) {
  try {
    if (!modelsLoaded) {
      await loadFaceApiModels();
    }
    
    // Detect face with landmarks and descriptor
    const detection = await faceapi
      .detectSingleFace(imageElement, new faceapi.TinyFaceDetectorOptions())
      .withFaceLandmarks()
      .withFaceDescriptor();
    
    if (!detection) {
      throw new Error('No face detected in image');
    }
    
    // Get the 128-dimensional descriptor
    const descriptor = Array.from(detection.descriptor);
    
    return {
      success: true,
      descriptor: descriptor,
      detection: detection
    };
  } catch (error) {
    console.error('Error detecting face:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

// Capture image from video stream and get face descriptor
async function captureFaceFromVideo(videoElement) {
  try {
    // Create canvas to capture video frame
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
    
    // Get base64 image
    const imageDataUrl = canvas.toDataURL('image/jpeg', 0.9);
    
    // Create image element for face detection
    const img = new Image();
    img.src = imageDataUrl;
    
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = reject;
    });
    
    // Detect face and get descriptor
    const result = await detectFaceAndGetDescriptor(img);
    
    if (result.success) {
      return {
        success: true,
        descriptor: result.descriptor,
        imageDataUrl: imageDataUrl
      };
    } else {
      return result;
    }
  } catch (error) {
    console.error('Error capturing face from video:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

// Initialize camera stream
async function initializeCamera(videoElement) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        facingMode: 'user'
      },
      audio: false
    });
    
    videoElement.srcObject = stream;
    
    return {
      success: true,
      stream: stream
    };
  } catch (error) {
    console.error('Error accessing camera:', error);
    return {
      success: false,
      error: error.message || 'Camera access denied'
    };
  }
}

// Stop camera stream
function stopCamera(videoElement) {
  if (videoElement && videoElement.srcObject) {
    const stream = videoElement.srcObject;
    const tracks = stream.getTracks();
    tracks.forEach(track => track.stop());
    videoElement.srcObject = null;
  }
}

// API functions for face recognition

async function registerEmployeeFace(employeeId, faceDescriptor, faceImage) {
  try {
    // Use apiPost to include authentication headers
    const data = await apiPost('/face/register', {
      employee_id: employeeId,
      face_descriptor: faceDescriptor,
      face_image: faceImage
    });
    
    return {
      success: true,
      data: data
    };
  } catch (error) {
    console.error('Error registering face:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

async function recognizeFace(faceDescriptor, storeId) {
  try {
    // Use apiPost to include authentication headers
    const data = await apiPost('/face/recognize', {
      face_descriptor: faceDescriptor,
      store_id: storeId
    });
    
    return {
      success: true,
      data: data
    };
  } catch (error) {
    console.error('Error recognizing face:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

async function clockInWithFace(faceDescriptor, faceImage, storeId) {
  try {
    // Use apiPost to include authentication headers
    const data = await apiPost('/timeclock/clock-in-face', {
      face_descriptor: faceDescriptor,
      face_image: faceImage,
      store_id: storeId
    });
    
    return {
      success: true,
      data: data
    };
  } catch (error) {
    console.error('Error clocking in:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

async function clockOutWithFace(faceDescriptor, faceImage, storeId) {
  try {
    // Use apiPost to include authentication headers
    const data = await apiPost('/timeclock/clock-out-face', {
      face_descriptor: faceDescriptor,
      face_image: faceImage,
      store_id: storeId
    });
    
    return {
      success: true,
      data: data
    };
  } catch (error) {
    console.error('Error clocking out:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

// Preload models when script loads
if (typeof faceapi !== 'undefined') {
  loadFaceApiModels().catch(console.error);
}
