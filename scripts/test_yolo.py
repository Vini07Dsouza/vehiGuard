import cv2
from ultralytics import YOLO

model = YOLO("yolov8n.pt")  # downloads the model the first time
results = model("https://ultralytics.com/images/bus.jpg")
cv2.imwrite("yolo_result.jpg", results[0].plot())
print("Saved yolo_result.jpg")
