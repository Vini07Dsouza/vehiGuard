import cv2

SOURCE = 0   # 0 = laptop webcam; try 1 or 2 for a phone-webcam app
cap = cv2.VideoCapture(SOURCE, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
print("Resolution:", cap.get(cv2.CAP_PROP_FRAME_WIDTH), "x", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

while True:
    ok, frame = cap.read()
    if not ok:
        print("Could not read frame")
        break
    cv2.imshow("Camera - press q or Esc to quit", frame)
    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
        break

cap.release()
cv2.destroyAllWindows()