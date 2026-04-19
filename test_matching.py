import sys
import os
import cv2
import numpy as np

def calculate_feature_match_score(img1_path, img2_path):
    try:
        # Load images in grayscale
        img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
        
        if img1 is None or img2 is None:
            return 0, 0

        # Preprocessing: Resize
        def resize_img(img, max_dim=800):
            h, w = img.shape
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                return cv2.resize(img, (int(w * scale), int(h * scale)))
            return img

        img1 = resize_img(img1)
        img2 = resize_img(img2)

        # Initialize SIFT detector
        sift = cv2.SIFT_create(contrastThreshold=0.01, edgeThreshold=15)

        # Find the keypoints and descriptors
        kp1, des1 = sift.detectAndCompute(img1, None)
        kp2, des2 = sift.detectAndCompute(img2, None)

        if des1 is None or des2 is None or len(kp1) < 5 or len(kp2) < 5:
            return 0, 0

        # FLANN parameters
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
        search_params = dict(checks=50)
        
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)

        # Apply Low's ratio test (0.7)
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.7 * n.distance:
                    good_matches.append(m)

        # RANSAC Homography Check
        if len(good_matches) >= 5:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            
            if mask is not None:
                inliers = int(np.sum(mask))
                return inliers, len(good_matches)
        
        return len(good_matches) // 2, len(good_matches)
    except Exception as e:
        print(f"Error: {e}")
        return 0, 0

if __name__ == "__main__":
    upload_dir = "static/uploads"
    files = [f for f in os.listdir(upload_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if len(files) < 2:
        print("Not enough images to test.")
        sys.exit(1)

    print(f"Found {len(files)} images. Testing first few pairs...")
    
    # Test a few pairs
    FEATURE_THRESHOLD = 6
    for i in range(min(5, len(files))):
        for j in range(i + 1, min(6, len(files))):
            f1 = files[i]
            f2 = files[j]
            p1 = os.path.join(upload_dir, f1)
            p2 = os.path.join(upload_dir, f2)
            
            inliers, good = calculate_feature_match_score(p1, p2)
            status = "MATCH!" if inliers >= FEATURE_THRESHOLD else "No match"
            print(f"Comparing {f1} and {f2}")
            print(f"  -> Good matches (Ratio Test): {good}")
            print(f"  -> Geometric Inliers (RANSAC): {inliers}")
            print(f"  -> Result: {status}")
            print("-" * 30)


            print(f"Comparing {f1} and {f2}")
            print(f"  -> Good matches (Ratio Test): {good}")
            print(f"  -> Geometric Inliers (RANSAC): {inliers}")
            print(f"  -> Result: {status}")
            print("-" * 30)
