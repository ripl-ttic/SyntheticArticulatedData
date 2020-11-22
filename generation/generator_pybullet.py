import time
import os
import csv
import copy
import math

import cv2
import pyro
import pyro.distributions as dist
import torch
import numpy as np
from tqdm import tqdm
import transforms3d as tf3d

import pybullet as p

from generation.mujocoCabinetParts import build_cabinet, sample_cabinet
from generation.mujocoDrawerParts import build_drawer, sample_drawers
from generation.mujocoMicrowaveParts import build_microwave, sample_microwave
from generation.mujocoToasterOvenParts import build_toaster, sample_toaster
from generation.mujocoDoubleCabinetParts import build_cabinet2, sample_cabinet2, set_two_door_control
from generation.mujocoRefrigeratorParts import build_refrigerator, sample_refrigerator
from generation.utils import *
import generation.calibrations as calibrations

p.connect(p.GUI)
p.setGravity(0,0,-100)

def white_bg(img):
    mask = 1 - (img > 0)
    img_cp = copy.deepcopy(img)
    img_cp[mask.all(axis=2)] = [255,255,255, 0]
    return img_cp

def buffer_to_real(z, zfar, znear):
    return 2*zfar*znear / (zfar + znear - (zfar - znear)*(2*z -1))

def vertical_flip(img):
    return np.flip(img, axis=0)

class SceneGenerator():
    def __init__(self, root_dir='bull/test_cabinets/solo', masked=False, debug_flag=False):
        '''
        Class for generating simulated articulated object dataset.
        params:
            - root_dir: save in this directory
            - start_idx: index of first image saved - useful in threading context
            - depth_data: np array of depth images
            - masked: should the background of depth images be 0s or 1s?
        '''
        self.scenes=[]
        self.savedir=root_dir
        self.masked = masked
        self.img_idx = 0
        self.depth_data=[]
        self.debugging=debug_flag

        # Camera external settings
        self.viewMatrix = p.computeViewMatrix(
            cameraEyePosition=[4,0,1],
            cameraTargetPosition=[0,0,1],
            cameraUpVector=[0,0,1]
        )

        # Camera internal settings
        self.projectionMatrix = p.computeProjectionMatrixFOV(
            fov=45.,
            aspect=1.0,
            nearVal=0.1,
            farVal=8.1
        )

        print(root_dir)

    def write_urdf(self, filename, xml):
        with open(filename, "w") as text_file:
            text_file.write(xml)

    def sample_obj(self, obj_type, mean_flag, left_only, cute_flag=False):
        if obj_type == 'microwave':
            l, w, h, t, left, mass = sample_microwave(mean_flag)
            if mean_flag:
                obj = build_microwave(l, w, h, t, left,
                                      set_pose = [1.0, 0.0, -0.15],
                                      set_rot = [0.0, 0.0, 0.0, 1.0] )
            elif cute_flag:
                base_xyz, base_angle = sample_pose()
                base_quat = angle_to_quat(base_angle)
                obj = build_microwave(l, w, h, t, left,
                                      set_pose = [1.0, 0.0, -0.15],
                                      set_rot = base_quat)
            else:
                obj = build_microwave(l, w, h, t, left)

            camera_dist = max(1.25, 2*math.log(10*h))
            camera_height = h/2.

        elif obj_type == 'drawer':
            l, w, h, t, left, mass = sample_drawers(mean_flag)
            if mean_flag:
                obj = build_drawer(l, w, h, t, left,
                                   set_pose = [1.5, 0.0, -0.4],
                                   set_rot = [0.0, 0.0, 0.0, 1.0] )
            elif cute_flag:
               base_xyz, base_angle = sample_pose()
               base_quat = angle_to_quat(base_angle)
               obj = build_drawer(l, w, h, t, left,
                                     set_pose = [1.2, 0.0, -0.15],
                                     set_rot = base_quat)
            else:
                obj = build_drawer(l, w, h, t, left)

            camera_dist = max(2, 2*math.log(10*h))
            camera_height = h/2.

        elif obj_type == 'toaster':
            l, w, h, t, left, mass = sample_toaster(mean_flag)
            if mean_flag:
                obj = build_toaster(l, w, h, t, left,
                                    set_pose = [1.5, 0.0, -0.3],
                                    set_rot = [0.0, 0.0, 0.0, 1.0] )
            elif cute_flag:
                base_xyz, base_angle = sample_pose()
                base_quat = angle_to_quat(base_angle)
                obj = build_toaster(l, w, h, t, left,
                                      set_pose = [1.0, 0.0, -0.15],
                                      set_rot = base_quat)
            else:
                obj = build_toaster(l, w, h, t, left)

            camera_dist = max(1, 2*math.log(10*h))
            camera_height = h/2.

        elif obj_type == 'cabinet':
            l, w, h, t, left, mass = sample_cabinet(mean_flag)
            if mean_flag:
                if left_only:
                    left=True
                else:
                    left=False
                obj = build_cabinet(l, w, h, t, left,
                                    set_pose = [1.5, 0.0, -0.3],
                                    set_rot = [0.0, 0.0, 0.0, 1.0] )
            elif cute_flag:
                base_xyz, base_angle = sample_pose()
                base_quat = angle_to_quat(base_angle)
                obj = build_cabinet(l, w, h, t, left,
                                      set_pose = [1.5, 0.0, -0.15],
                                      set_rot = base_quat)
            else:
                left = np.random.choice([True,False])
                obj = build_cabinet(l, w, h, t, left)
            
            camera_dist = 2*math.log(10*h)
            camera_height = h/2.

        elif obj_type == 'cabinet2':
            l, w, h, t, left, mass = sample_cabinet2(mean_flag)
            if mean_flag:
                obj = build_cabinet2(l, w, h, t, left,
                                     set_pose = [1.5, 0.0, -0.3],
                                     set_rot = [0.0, 0.0, 0.0, 1.0] )
            elif cute_flag:
                base_xyz, base_angle = sample_pose()
                base_quat = angle_to_quat(base_angle)
                obj = build_cabinet2(l, w, h, t, left,
                                      set_pose = [1.5, 0.0, -0.15],
                                      set_rot = base_quat)
            else:
                obj = build_cabinet2(l, w, h, t, left)

            camera_dist = 2*math.log(10*h)
            camera_height = h/2.

        elif obj_type == 'refrigerator':
            l, w, h, t, left, mass = sample_refrigerator(mean_flag)
            if mean_flag:

                obj = build_refrigerator(l, w, h, t, left,
                                         set_pose = [1.5, 0.0, -0.3],
                                         set_rot = [0.0, 0.0, 0.0, 1.0])
            elif cute_flag:
                base_xyz, base_angle = sample_pose()
                base_quat = angle_to_quat(base_angle)
                obj = build_refrigerator(l, w, h, t, left,
                                      set_pose = [2.5, 0.0, -0.75],
                                      set_rot = base_quat)

            else:
                obj = build_refrigerator(l, w, h, t, left)

            camera_dist = 2*math.log(10*h)
            camera_height = h/2.

        else:
            raise 'uh oh, object not implemented!'
        return obj, camera_dist, camera_height

    def generate_scenes(self, N, objtype, write_csv=True, save_imgs=True, mean_flag=False, left_only=False, cute_flag=False):
        fname=os.path.join(self.savedir, 'params.csv')
        self.img_idx = 0
        with open(fname, 'a') as csvfile:
            writ = csv.writer(csvfile, delimiter=',')
            for i in tqdm(range(N)):
                obj, camera_dist, camera_height = self.sample_obj(objtype, mean_flag, left_only, cute_flag=cute_flag)
                xml=obj.xml
                fname=os.path.join(self.savedir, 'scene'+str(i).zfill(6)+'.xml')
                self.write_urdf(fname, xml)
                self.scenes.append(fname)
                self.take_images(fname, obj, camera_dist, camera_height, writ)
        return

    def take_images(self, filename, obj, camera_dist, camera_height, writer, img_idx=0, debug=False):
        objId, _ = p.loadMJCF(filename)

        self.viewMatrix = p.computeViewMatrix(
            cameraEyePosition=[camera_dist,0,3*camera_height],
            cameraTargetPosition=[0,0,camera_height],
            cameraUpVector=[1,0,1]
        )
        
        # Take 16 pictures, permuting orientation and joint extension
        for t in range(1,4000):
            p.stepSimulation()

            if t%250==0:
                # Randomly update orientation to new orientation between -pi/4 and pi/4
                startPos = [0,0,0]
                rotation = np.random.uniform(-np.pi/4.,np.pi/4.)
                startOrientation = p.getQuaternionFromEuler([0,0,rotation])
                p.resetBasePositionAndOrientation(objId, startPos, startOrientation)
                
                # Update joint extension randomly between 0 and 120
                for j in range(p.getNumJoints(objId)):
                    if obj.control[j] < 0:
                        rotation = np.random.uniform(obj.control[j], 0)
                    else: 
                        rotation = np.random.uniform(0, obj.control[j])
                    p.resetJointState(objId, j, rotation)

                #########################
                IMG_WIDTH = calibrations.sim_width
                IMG_HEIGHT = calibrations.sim_height
                #########################

                # Take picture
                width, height, img, depth, segImg = p.getCameraImage(
                    IMG_WIDTH, # width
                    IMG_HEIGHT, # height
                    self.viewMatrix,
                    self.projectionMatrix, 
                    lightDirection=[camera_dist, 0, camera_height+1], # light source
                    shadow=1, # include shadows
                )
                
                depth = vertical_flip(depth)
                real_depth = buffer_to_real(depth, 12.0, 0.1)
                norm_depth = real_depth / 12.0

                if self.masked:
                    # remove background
                    mask = norm_depth > 0.99
                    norm_depth = (1-mask)*norm_depth

                if self.debugging:
                    # save image to disk for visualization
                    # img = cv2.resize(img, (IMG_WIDTH,IMG_HEIGHT))

                    #img = vertical_flip(img)
                    img = white_bg(img)
                    imgfname = os.path.join(self.savedir, 'img'+str(self.img_idx).zfill(6)+'.png')
                    depth_imgfname = os.path.join(self.savedir, 'depth_img'+str(self.img_idx).zfill(6)+'.png')
                    integer_depth = norm_depth * 255
                    cv2.imwrite(imgfname, img)
                    cv2.imwrite(depth_imgfname, integer_depth)

                # if IMG_WIDTH != 192 or IMG_HEIGHT != 108:
                #     depth = cv2.resize(norm_depth, (192,108))

                depthfname = os.path.join(self.savedir,'depth'+str(self.img_idx).zfill(6) + '.pt')
                torch.save(torch.tensor(norm_depth.copy()), depthfname)
                row = np.array([img_idx, rotation]) # SAVE SCREW REPRESENTATION HERE 
                # print(row.shape)
                writer.writerow(row)
                self.img_idx += 1