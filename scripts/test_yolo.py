import cv2
from ultralytics import YOLO

model = YOLO("yolov8n.pt")  # downloads the model the first time
results = model("https://ultralytics.com/images/bus.jpg")
cv2.imshow("YOLO test - press any key", results[0].plot())
cv2.waitKey(0)
cv2.destroyAllWindows()
