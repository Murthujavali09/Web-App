// timeclock-handler.js
// Handles the timeclock page logic with face recognition

document.addEventListener('DOMContentLoaded', async () => {
  // Only run on timeclock page
  if (!document.getElementById('timeclockTabRoot')) return;
  
  // Get session
  const session = loadSession();
  if (!session || session.role !== 'store') {
    window.location = 'login.html';
    return;
  }
  
  const storeId = session.storeId || session.storeName;
  
  // Get elements
  const statusText = document.getElementById('statusText');
  const timeDisplay = document.getElementById('timeDisplay');
  const clockInBtn = document.getElementById('clockInBtn');
  const clockOutBtn = document.getElementById('clockOutBtn');
  const cameraContainer = document.getElementById('cameraContainer');
  const video = document.getElementById('video');
  const captureBtn = document.getElementById('captureBtn');
  const cancelCameraBtn = document.getElementById('cancelCameraBtn');
  const photoPreview = document.getElementById('photoPreview');
  const capturedPhoto = document.getElementById('capturedPhoto');
  const recognitionResult = document.getElementById('recognitionResult');
  const confirmPhotoBtn = document.getElementById('confirmPhotoBtn');
  const retakeBtn = document.getElementById('retakeBtn');
  const loadingIndicator = document.getElementById('loadingIndicator');
  const currentClockStatus = document.getElementById('currentClockStatus');
  const clockedInEmployeeName = document.getElementById('clockedInEmployeeName');
  const clockInTime = document.getElementById('clockInTime');
  const clockOutTime = document.getElementById('clockOutTime');
  
  let currentAction = null; // 'clock-in' or 'clock-out'
  let capturedData = null; // Stores captured face data
  
  // Update time display
  function updateTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    if (timeDisplay) {
      timeDisplay.textContent = timeStr;
    }
  }
  
  setInterval(updateTime, 1000);
  updateTime();
  
  // Fetch and display current clock-in status
  async function fetchCurrentClockStatus() {
    try {
      // Use apiGet to include authentication headers
      const data = await apiGet(`/timeclock/today`, { store_id: storeId });
      
      // Find currently clocked-in employee (clock_out is null)
      const activeEntry = data.employees?.find(emp => !emp.clock_out);
      
      if (activeEntry && currentClockStatus) {
        // Show the status card
        currentClockStatus.classList.remove('hidden');
        
        // Update employee name
        if (clockedInEmployeeName) {
          clockedInEmployeeName.textContent = activeEntry.employee_name || 'Unknown Employee';
        }
        
        // Update clock-in time
        if (clockInTime && activeEntry.clock_in) {
          const clockInDate = new Date(activeEntry.clock_in);
          const clockInStr = clockInDate.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
          });
          clockInTime.textContent = clockInStr;
        }
        
        // Update clock-out time
        if (clockOutTime) {
          if (activeEntry.clock_out) {
            const clockOutDate = new Date(activeEntry.clock_out);
            const clockOutStr = clockOutDate.toLocaleTimeString('en-US', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hour12: true
            });
            clockOutTime.textContent = clockOutStr;
          } else {
            clockOutTime.textContent = 'Not clocked out';
          }
        }
      } else {
        // Hide the status card if no one is clocked in
        if (currentClockStatus) {
          currentClockStatus.classList.add('hidden');
        }
      }
    } catch (error) {
      console.error('Error fetching clock status:', error);
      // Hide status card on error
      if (currentClockStatus) {
        currentClockStatus.classList.add('hidden');
      }
    }
  }
  
  // Fetch status on page load
  fetchCurrentClockStatus();
  
  // Refresh status every 30 seconds
  setInterval(fetchCurrentClockStatus, 30000);
  
  // Show loading
  function showLoading(show = true) {
    if (loadingIndicator) {
      loadingIndicator.style.display = show ? 'block' : 'none';
    }
  }
  
  // Update status
  function updateStatus(text, color = '#6c757d') {
    if (statusText) {
      statusText.textContent = text;
      statusText.style.color = color;
    }
  }
  
  // Show camera
  async function showCamera(action) {
    currentAction = action;
    
    // Hide buttons and preview
    if (document.getElementById('clockButtons')) {
      document.getElementById('clockButtons').style.display = 'none';
    }
    if (photoPreview) photoPreview.style.display = 'none';
    
    // Show camera container
    if (cameraContainer) cameraContainer.style.display = 'block';
    
    updateStatus(`Position your face in the camera for ${action === 'clock-in' ? 'Clock In' : 'Clock Out'}`, '#007bff');
    
    // Initialize camera
    const result = await initializeCamera(video);
    
    if (!result.success) {
      showError('Failed to access camera: ' + result.error);
      hideCamera();
      return;
    }
    
    // Load face-api models if not loaded
    showLoading(true);
    updateStatus('Loading face recognition models...', '#007bff');
    
    const modelsLoaded = await loadFaceApiModels();
    
    showLoading(false);
    
    if (!modelsLoaded) {
      showError('Failed to load face recognition models. Please refresh the page.');
      hideCamera();
      return;
    }
    
    updateStatus(`Ready! Position your face in the camera`, '#28a745');
  }
  
  // Hide camera
  function hideCamera() {
    stopCamera(video);
    
    if (cameraContainer) cameraContainer.style.display = 'none';
    if (photoPreview) photoPreview.style.display = 'none';
    if (document.getElementById('clockButtons')) {
      document.getElementById('clockButtons').style.display = 'flex';
    }
    
    // Reset confirm button state
    if (confirmPhotoBtn) {
      confirmPhotoBtn.disabled = false;
      confirmPhotoBtn.style.opacity = '1';
      confirmPhotoBtn.style.cursor = 'pointer';
    }
    
    currentAction = null;
    capturedData = null;
    
    updateStatus('Ready to Clock In or Clock Out', '#6c757d');
  }
  
  // Capture face
  async function captureFace() {
    showLoading(true);
    updateStatus('Detecting face...', '#007bff');
    
    const result = await captureFaceFromVideo(video);
    
    showLoading(false);
    
    if (!result.success) {
      showError('Failed to detect face: ' + result.error + '\n\nPlease ensure:\n- Your face is clearly visible\n- Good lighting\n- Look directly at the camera', 'Face Detection Failed');
      return;
    }
    
    // Store captured data
    capturedData = {
      descriptor: result.descriptor,
      imageDataUrl: result.imageDataUrl
    };
    
    // Stop camera
    stopCamera(video);
    
    // Show preview
    if (cameraContainer) cameraContainer.style.display = 'none';
    if (photoPreview) photoPreview.style.display = 'block';
    if (capturedPhoto) capturedPhoto.src = result.imageDataUrl;
    
    // Disable confirm button initially (will be enabled after successful recognition)
    if (confirmPhotoBtn) {
      confirmPhotoBtn.disabled = true;
      confirmPhotoBtn.style.opacity = '0.5';
      confirmPhotoBtn.style.cursor = 'not-allowed';
    }
    
    // Recognize face
    updateStatus('Recognizing face...', '#007bff');
    showLoading(true);
    
    const recognizeResult = await recognizeFace(result.descriptor, storeId);
    
    showLoading(false);
    
    // Track if face is recognized (for enabling/disabling confirm button)
    let faceRecognized = false;
    
    if (recognizeResult.success) {
      const employee = recognizeResult.data;
      const confidence = employee.confidence || 0;
      const confidencePercent = (confidence * 100).toFixed(1);
      
      // Check if confidence is high enough (minimum 30%)
      const MIN_CONFIDENCE = 0.3;
      
      if (confidence < MIN_CONFIDENCE) {
        // Confidence too low - treat as unrecognized
        faceRecognized = false;
        
        if (confirmPhotoBtn) {
          confirmPhotoBtn.disabled = true;
          confirmPhotoBtn.style.opacity = '0.5';
          confirmPhotoBtn.style.cursor = 'not-allowed';
        }
        
        if (recognitionResult) {
          recognitionResult.innerHTML = `
            <div style="color:#dc3545;font-size:1.2rem;font-weight:600;margin-bottom:8px;">
              ⚠️ Low Confidence Match
            </div>
            <div style="color:#6c757d;font-size:0.9rem;margin-bottom:12px;">
              Face matched to "${employee.employee_name}" but confidence is too low (${confidencePercent}%). This may not be you.
            </div>
            <div style="padding:12px;background:#fff3cd;border-radius:8px;margin-top:12px;border:1px solid #ffc107;">
              <div style="color:#856404;font-size:0.9rem;font-weight:600;margin-bottom:8px;">
                Need to Register Your Face?
              </div>
              <div style="color:#856404;font-size:0.85rem;margin-bottom:12px;">
                If this is your face, please contact your manager to register or update your face in the system.
              </div>
              <div style="color:#856404;font-size:0.75rem;text-align:center;">
                You cannot clock in/out until your face is properly registered.
              </div>
            </div>
          `;
        }
        
        updateStatus('Face not recognized. Please contact your manager to register your face.', '#dc3545');
      } else {
        // Confidence is high enough
        faceRecognized = true;
        
        if (recognitionResult) {
          recognitionResult.innerHTML = `
            <div style="color:#28a745;font-size:1.2rem;font-weight:600;margin-bottom:8px;">
              ✅ Face Recognized
            </div>
            <div style="color:#2c3e50;font-size:1.1rem;margin-bottom:4px;">
              <strong>${employee.employee_name}</strong>
            </div>
            <div style="color:#6c757d;font-size:0.9rem;">
              Confidence: ${confidencePercent}%
            </div>
          `;
        }
        
        // Enable confirm button when face is recognized
        if (confirmPhotoBtn) {
          confirmPhotoBtn.disabled = false;
          confirmPhotoBtn.style.opacity = '1';
          confirmPhotoBtn.style.cursor = 'pointer';
        }
        
        updateStatus(`Face recognized: ${employee.employee_name}`, '#28a745');
      }
    } else {
      faceRecognized = false;
      
      // Disable confirm button when face is not recognized
      if (confirmPhotoBtn) {
        confirmPhotoBtn.disabled = true;
        confirmPhotoBtn.style.opacity = '0.5';
        confirmPhotoBtn.style.cursor = 'not-allowed';
      }
      
      if (recognitionResult) {
        recognitionResult.innerHTML = `
          <div style="color:#dc3545;font-size:1.2rem;font-weight:600;margin-bottom:8px;">
            ❌ Face Not Recognized
          </div>
          <div style="color:#6c757d;font-size:0.9rem;margin-bottom:12px;">
            ${recognizeResult.error || 'Face not recognized. You cannot clock in/out until your face is recognized.'}
          </div>
          <div style="padding:12px;background:#fff3cd;border-radius:8px;margin-top:12px;border:1px solid #ffc107;">
            <div style="color:#856404;font-size:0.9rem;font-weight:600;margin-bottom:8px;">
              Need to Register Your Face?
            </div>
            <div style="color:#856404;font-size:0.85rem;margin-bottom:12px;">
              If you haven't registered your face yet, or if your appearance has changed significantly, please contact your manager to register or update your face in the system.
            </div>
            <div style="color:#856404;font-size:0.75rem;text-align:center;margin-top:8px;">
              You cannot clock in/out until your face is properly registered by your manager.
            </div>
          </div>
        `;
        
        // Add event listener for add appearance button
        const addAppearanceBtn = document.getElementById('addAppearanceBtn');
        if (addAppearanceBtn) {
          addAppearanceBtn.addEventListener('click', async () => {
            const employeeName = document.getElementById('employeeNameInput')?.value.trim();
            if (!employeeName) {
              showError('Please enter your name');
              return;
            }
            
            if (!capturedData) {
              showError('No face data captured. Please retake photo.');
              return;
            }
            
            showLoading(true);
            updateStatus('Adding new appearance...', '#007bff');
            
            try {
              // Use apiPost to include authentication headers
              const data = await apiPost('/face/add-appearance', {
                employee_name: employeeName,
                face_descriptor: capturedData.descriptor,
                face_image: capturedData.imageDataUrl
              });
              
              showLoading(false);
              
              if (data.success) {
                showInfo(`✅ New appearance added successfully!\n\nYou now have ${data.total_registrations} registered appearance(s).\n\nRetrying face recognition...`);
                
                // Retry face recognition after adding appearance
                showLoading(true);
                updateStatus('Retrying face recognition...', '#007bff');
                
                const retryResult = await recognizeFace(capturedData.descriptor, storeId);
                
                showLoading(false);
                
                if (retryResult.success) {
                  const employee = retryResult.data;
                  const confidence = employee.confidence || 0;
                  const confidencePercent = (confidence * 100).toFixed(1);
                  const MIN_CONFIDENCE = 0.3;
                  
                  if (confidence < MIN_CONFIDENCE) {
                    // Still too low confidence
                    faceRecognized = false;
                    if (confirmPhotoBtn) {
                      confirmPhotoBtn.disabled = true;
                      confirmPhotoBtn.style.opacity = '0.5';
                      confirmPhotoBtn.style.cursor = 'not-allowed';
                    }
                    if (recognitionResult) {
                      recognitionResult.innerHTML = `
                        <div style="color:#dc3545;font-size:1.2rem;font-weight:600;margin-bottom:8px;">
                          ⚠️ Still Low Confidence
                        </div>
                        <div style="color:#6c757d;font-size:0.9rem;margin-bottom:12px;">
                          Confidence is still too low (${confidencePercent}%). Please contact your manager to register your face.
                        </div>
                      `;
                    }
                    updateStatus('Face still not recognized. Please contact your manager.', '#dc3545');
                  } else {
                    faceRecognized = true;
                    
                    if (recognitionResult) {
                      recognitionResult.innerHTML = `
                        <div style="color:#28a745;font-size:1.2rem;font-weight:600;margin-bottom:8px;">
                          ✅ Face Recognized
                        </div>
                        <div style="color:#2c3e50;font-size:1.1rem;margin-bottom:4px;">
                          <strong>${employee.employee_name}</strong>
                        </div>
                        <div style="color:#6c757d;font-size:0.9rem;">
                          Confidence: ${confidencePercent}%
                        </div>
                      `;
                    }
                    
                    // Enable confirm button after successful recognition
                    if (confirmPhotoBtn) {
                      confirmPhotoBtn.disabled = false;
                      confirmPhotoBtn.style.opacity = '1';
                      confirmPhotoBtn.style.cursor = 'pointer';
                    }
                    
                    updateStatus(`Face recognized: ${employee.employee_name}`, '#28a745');
                  }
                } else {
                  // Still not recognized even after adding appearance
                  if (recognitionResult) {
                    recognitionResult.innerHTML = `
                      <div style="color:#dc3545;font-size:1.2rem;font-weight:600;margin-bottom:8px;">
                        ❌ Still Not Recognized
                      </div>
                      <div style="color:#6c757d;font-size:0.9rem;margin-bottom:12px;">
                        Your new appearance was added, but face recognition still failed. Please try retaking the photo or contact your manager.
                      </div>
                    `;
                  }
                  
                  updateStatus('Face still not recognized. Please retake photo.', '#dc3545');
                }
              } else {
                showError('Failed to add appearance: ' + (data.error || 'Unknown error'));
              }
            } catch (err) {
              showLoading(false);
              showError('Failed to add appearance: ' + err.message);
            }
          });
        }
      }
      
      updateStatus('Face not recognized. Cannot proceed until recognized.', '#dc3545');
    }
  }
  
  // Confirm and process
  async function confirmAndProcess() {
    if (!capturedData) {
      showWarning('No face data captured');
      return;
    }
    
    // Double-check face recognition before proceeding
    showLoading(true);
    updateStatus('Verifying face recognition...', '#007bff');
    
    const verifyResult = await recognizeFace(capturedData.descriptor, storeId);
    
    if (!verifyResult.success) {
      showLoading(false);
      showError('Face not recognized. Please ensure your face is recognized before proceeding.\n\nYou can add a new appearance if your appearance has changed.');
      return;
    }
    
    updateStatus('Processing...', '#007bff');
    
    let result;
    
    if (currentAction === 'clock-in') {
      result = await clockInWithFace(capturedData.descriptor, capturedData.imageDataUrl, storeId);
    } else if (currentAction === 'clock-out') {
      result = await clockOutWithFace(capturedData.descriptor, capturedData.imageDataUrl, storeId);
    }
    
    showLoading(false);
    
    if (result && result.success) {
      const data = result.data;
      const actionText = currentAction === 'clock-in' ? 'Clocked In' : 'Clocked Out';
      const time = new Date(currentAction === 'clock-in' ? data.clock_in_time : data.clock_out_time);
      const timeStr = time.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      });
      
      updateStatus(`✅ ${actionText} Successfully!`, '#28a745');
      
      let message = `${actionText} Successfully!\n\n`;
      message += `Employee: ${data.employee_name}\n`;
      message += `Time: ${timeStr}\n`;
      
      if (currentAction === 'clock-out' && data.hours_worked) {
        message += `Hours Worked: ${data.hours_worked} hours`;
      }
      
      showInfo(message);
      
      // Reset
      hideCamera();
      
      // Refresh clock status after successful clock in/out
      setTimeout(fetchCurrentClockStatus, 1000);
    } else {
      const errorMsg = result ? result.error : 'Unknown error occurred';
      updateStatus(`❌ Failed: ${errorMsg}`, '#dc3545');
      showError('Failed to ' + (currentAction === 'clock-in' ? 'clock in' : 'clock out') + ':\n\n' + errorMsg);
    }
  }
  
  // Event listeners
  if (clockInBtn) {
    clockInBtn.addEventListener('click', () => {
      showCamera('clock-in');
    });
  }
  
  if (clockOutBtn) {
    clockOutBtn.addEventListener('click', () => {
      showCamera('clock-out');
    });
  }
  
  if (captureBtn) {
    captureBtn.addEventListener('click', captureFace);
  }
  
  if (cancelCameraBtn) {
    cancelCameraBtn.addEventListener('click', hideCamera);
  }
  
  if (confirmPhotoBtn) {
    confirmPhotoBtn.addEventListener('click', confirmAndProcess);
  }
  
  if (retakeBtn) {
    retakeBtn.addEventListener('click', () => {
      if (photoPreview) photoPreview.style.display = 'none';
      showCamera(currentAction);
    });
  }
});
