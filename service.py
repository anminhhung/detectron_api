from flask import Flask, render_template, Response, request, jsonify

import cv2
import numpy as np 
import time
import logging
import traceback
import os
import io
import requests
import random
import json

from utils.utils import load_class_names
from utils.parser import get_config
from utils.draw import draw_bbox

from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg as config_detectron

from src.predict import predict

# setup config
cfg = get_config()
cfg.merge_from_file('configs/service.yaml')
cfg.merge_from_file('configs/rcode.yaml')

# create log_file, rcode
LOG_PATH = cfg.SERVICE.LOG_PATH
RCODE = cfg.RCODE

if not os.path.exists(LOG_PATH):
    os.mkdir(LOG_PATH)

# setup host, port
HOST = cfg.SERVICE.SERVICE_IP
PORT = cfg.SERVICE.PORT

# logging
logging.basicConfig(filename=os.path.join(LOG_PATH, str(time.time())+".log"), filemode="w", level=logging.DEBUG, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console = logging.StreamHandler()
console.setLevel(logging.ERROR)
logging.getLogger("").addHandler(console)
logger = logging.getLogger(__name__)

# set up detectron
path_weigth = cfg.SERVICE.DETECT_WEIGHT
path_config = cfg.SERVICE.DETECT_CONFIG
confidences_threshold = cfg.SERVICE.THRESHOLD
num_of_class = cfg.SERVICE.NUMBER_CLASS

detectron = config_detectron()
detectron.MODEL.DEVICE= cfg.SERVICE.DEVICE
detectron.merge_from_file(path_config)
detectron.MODEL.WEIGHTS = path_weigth

detectron.MODEL.ROI_HEADS.SCORE_THRESH_TEST = confidences_threshold
detectron.MODEL.ROI_HEADS.NUM_CLASSES = num_of_class

PREDICTOR = DefaultPredictor(detectron)

# create labels
CLASSES = load_class_names(cfg.SERVICE.CLASSES)

# init app
app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict_image():
    if request.method == 'POST':
        file = request.files['file']
        image_file = file.read()
        image = cv2.imdecode(np.frombuffer(image_file, dtype=np.uint8), -1)
        
        height, width, channels = image.shape 
        center_image = (width//2, height//2)
        list_boxes, list_scores, list_classes = predict(image, PREDICTOR, CLASSES)

        # draw
        image = draw_bbox(image, list_boxes, list_scores, list_classes)
        cv2.imwrite("image.jpg", image)

        i = 0
        len_boxes = len(list_boxes)
        point_tl = None 
        point_tr = None 
        point_bl = None 
        point_br = None

        while i<len_boxes:
            bbox = list_boxes[i]
            x1 = bbox[0]
            y1 = bbox[1]
            x2 = bbox[2]
            y2 = bbox[3]
            w = x2 - x1
            h = y2 - y1
            center_x = x1 + w//2
            center_y = y1 + h//2
            center = (center_x, center_y)
            # print("max: ", (x1, y1))
            # print("min: ", (x2, y2))
            # if list_classes[i] == 'top_right':
            #     point_tr = center
            # elif list_classes[i] == 'bottom_left':
            #     point_bl = center
            # elif list_classes[i] == 'bottom_right':
            #     point_br = center 
            # else:
            #     point_tl = center 
            
            if center[0] < center_image[0] and center[1] < center_image[1]:
                point_tl = center
            elif center[0] > center_image[0] and center[1] < center_image[1]:
                point_tr = center
            elif center[0] > center_image[0] and center[1] > center_image[1]:
                point_br = center 
            else:
                point_bl = center

            i += 1
        
        result = {'point_tl': point_tl, 'point_tr': point_tr, 'point_bl': point_bl, 'point_br': point_br}
    
    return result
        


if __name__ == '__main__':
    app.run(host=HOST, port=PORT)
