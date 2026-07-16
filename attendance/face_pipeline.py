import io
import json
import dlib
import numpy as np
from PIL import Image
import face_recognition_models
from sklearn.svm import SVC

class FacePipeline:
    def __init__(self):
        """
        Initialize the structural AI models using weights supplied by 
        the face_recognition_models library.
        """
        # Initializing dlib's HoG face locator
        self.detector = dlib.get_frontal_face_detector()
        
        # Loading the 68-point facial landmark pose predictor file path
        predictor_path = face_recognition_models.pose_predictor_model_location()
        self.sp = dlib.shape_predictor(predictor_path)
        
        # Loading the deep learning ResNet vector encoder file path
        resnet_path = face_recognition_models.face_recognition_model_location()
        self.face_encoder = dlib.face_recognition_model_v1(resnet_path)

    def extract_multiple_embeddings(self, uploaded_file):
        """
        Scans an image, processes EVERY face detected, and returns a list of
        dictionaries containing the 128D vectors and their bounding box coordinates.
        """
        try:
            # Step 1: Initialize the data stream pointer back to zero
            uploaded_file.seek(0)
            img_bytes = uploaded_file.read()
            
            # Step 2: Load binary bytes into a Pillow canvas and enforce RGB channels
            pil_image = Image.open(io.BytesIO(img_bytes))
            rgb_image = pil_image.convert('RGB')
            
            # Step 3: Convert the Pillow image instance into a standard NumPy pixel matrix
            img_array = np.array(rgb_image)
            
            # Step 4: Scan the entire matrix layer to detect all face boundaries
            detected_faces = self.detector(img_array, 1)
            
            # Step 5: Instantiate a blank list container to gather extracted face payloads
            found_faces_data = []
            
            # Step 6: Loop through every single face block identified by the detector
            for face_rect in detected_faces:
                
                # Step 7: Map the 68 structural geometric landmark coordinates for this specific face
                shape = self.sp(img_array, face_rect)
                
                # Step 8: Pass the pixel matrix and landmarks to compute the 128D vector array
                face_descriptor = self.face_encoder.compute_face_descriptor(img_array, shape, num_jitters=1)
                
                # Step 9: Bundle the structural coordinates and vector values into a dictionary profile
                face_profile = {
                    "box_coordinates": (face_rect.left(), face_rect.top(), face_rect.right(), face_rect.bottom()),
                    "embedding": list(face_descriptor)
                }
                
                # Step 10: Append this individual profile block into our final array ledger
                found_faces_data.append(face_profile)
                
            # Step 11: Return the compiled batch of faces back to the calling controller view
            return found_faces_data
            
        except Exception as e:
            print(f"Group Extraction Pipeline Exception Error: {e}")
            return []

    def train_svm_classifier(self):
        """
        Queries all registered student profiles from the database, builds an
        N-class spatial dataset, and fits an SVM boundary classifier model.
        """
        from users.models import StudentProfile 
        
        profiles = StudentProfile.objects.filter(is_face_registered=True)
        
        if not profiles.exists():
            print("Training Intercepted: No verified biometric nodes present in database.")
            return None
            
        X = []  
        y = []  
        
        for profile in profiles:
            if profile.face_encoding:
                vector = json.loads(profile.face_encoding)
                X.append(vector)
                y.append(profile.roll_number)
                
        if len(X) == 0:
            print("Training Aborted: Zero structural encodings found in records.")
            return None
            
        X_train = np.array(X)
        y_train = np.array(y)
        
        clf = SVC(kernel='linear', probability=True, class_weight='balanced')
        clf.fit(X_train, y_train)
        
        print(f"System Matrix Synced: SVM successfully calibrated to {len(X_train)} student nodes.")
        return clf