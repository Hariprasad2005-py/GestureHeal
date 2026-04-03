"""
modules/gesture_detector.py
MediaPipe-based real-time hand landmark detection and gesture classification.

Detects:
  - raise      : wrist above shoulder-level (high Y position)
  - swipe_left : index tip moving left rapidly
  - swipe_right: index tip moving right rapidly
  - wrist_rot  : wrist tilt / rotation (pronation-supination)
  - pinch      : thumb-index distance < threshold
  - open_hand  : all fingers extended
"""

import mediapipe as mp
import numpy as np
import math
import time


class GestureDetector:
    # MediaPipe landmark indices
    WRIST         = 0
    THUMB_TIP     = 4
    INDEX_MCP     = 5
    INDEX_TIP     = 8
    MIDDLE_TIP    = 12
    RING_TIP      = 16
    PINKY_TIP     = 20
    INDEX_PIP     = 6
    MIDDLE_PIP    = 10
    RING_PIP      = 14
    PINKY_PIP     = 18

    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.mp_draw  = mp.solutions.drawing_utils
        self.mp_styles= mp.solutions.drawing_styles

        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.70,
            min_tracking_confidence=0.60,
            model_complexity=1,
        )

        # Velocity tracking for swipe detection
        self._prev_x    = {}   # hand_label -> prev x
        self._prev_time = {}
        self._vel_x     = {}   # smoothed velocity

    # ──────────────────────────────────────────────────────────────────────────
    def process(self, frame_rgb):
        """
        Run MediaPipe inference on an RGB frame.
        Returns a dict with all extracted features, or None if no hand found.
        """
        results = self.hands.process(frame_rgb)
        h, w, _ = frame_rgb.shape

        output = {
            "detected"       : False,
            "gesture"        : None,
            "index_tip_norm" : (0.5, 0.5),
            "wrist_angle"    : 0.0,
            "wrist_height"   : 0.5,   # normalized 0=top, 1=bottom
            "fingers_up"     : [],
            "num_hands"      : 0,
            "landmarks_raw"  : [],
            "bilateral"      : False,
            "rom_degrees"    : 0.0,
            "hands"          : [],
        }

        if not results.multi_hand_landmarks:
            return output

        output["detected"]  = True
        output["num_hands"] = len(results.multi_hand_landmarks)
        output["bilateral"] = output["num_hands"] >= 2

        # Process each detected hand
        for i, hand_lm in enumerate(results.multi_hand_landmarks):
            lm = hand_lm.landmark
            if results.multi_handedness and i < len(results.multi_handedness):
                handedness = results.multi_handedness[i].classification[0].label
            else:
                handedness = f"hand_{i}"

            def pt(idx): return (lm[idx].x, lm[idx].y, lm[idx].z)
            wrist     = pt(self.WRIST)
            index_tip = pt(self.INDEX_TIP)
            thumb_tip = pt(self.THUMB_TIP)

            fingers_up = self._count_fingers(lm)
            wrist_angle = self._wrist_rotation_angle(lm)

            # ── Velocity (swipe detection) ──
            now = time.time()
            label = handedness
            if label in self._prev_x and (now - self._prev_time[label]) > 0:
                dt  = now - self._prev_time[label]
                raw_vel = (index_tip[0] - self._prev_x[label]) / dt
                alpha = 0.6
                self._vel_x[label] = alpha * raw_vel + (1 - alpha) * self._vel_x.get(label, 0)
            self._prev_x[label]    = index_tip[0]
            self._prev_time[label] = now

            vel = self._vel_x.get(label, 0)

            gesture = self._classify_gesture(
                wrist, index_tip, thumb_tip, fingers_up, vel, wrist_angle
            )

            hand_entry = {
                "label"          : handedness,
                "gesture"        : gesture,
                "index_tip_norm" : (index_tip[0], index_tip[1]),
                "wrist_angle"    : wrist_angle,
                "wrist_height"   : wrist[1],
                "fingers_up"     : fingers_up,
                "landmarks_raw"  : [(l.x, l.y, l.z) for l in lm],
                "rom_degrees"    : abs(wrist_angle),
            }
            output["hands"].append(hand_entry)

        # Use first detected hand as primary (backward compatible fields)
        primary = output["hands"][0]
        output["gesture"]        = primary["gesture"]
        output["index_tip_norm"] = primary["index_tip_norm"]
        output["wrist_angle"]    = primary["wrist_angle"]
        output["wrist_height"]   = primary["wrist_height"]
        output["fingers_up"]     = primary["fingers_up"]
        output["landmarks_raw"]  = primary["landmarks_raw"]
        output["rom_degrees"]    = primary["rom_degrees"]

        return output

    # ──────────────────────────────────────────────────────────────────────────
    def _classify_gesture(self, wrist, index_tip, thumb_tip, fingers_up, vel_x, wrist_angle):
        """
        Rule-based gesture classification.
        Priority: swipe > raise > wrist_rot > pinch > open_hand
        Swipe is checked FIRST so left/right hand movement always registers.
        """
        # SWIPE LEFT / RIGHT — checked first, low threshold
        # 0.18 units/sec in normalized space = a casual hand sweep
        SWIPE_THRESH = 0.18
        if vel_x < -SWIPE_THRESH:
            return "swipe_left"
        if vel_x > SWIPE_THRESH:
            return "swipe_right"

        # RAISE: wrist high on screen (y < 0.45 in normalized coords)
        if wrist[1] < 0.45:
            return "raise"

        # WRIST ROTATION: large tilt angle
        if abs(wrist_angle) > 20:
            return "wrist_rot"

        # PINCH: thumb tip close to index tip
        thumb_idx_dist = math.dist(thumb_tip[:2], index_tip[:2])
        if thumb_idx_dist < 0.07:
            return "pinch"

        # OPEN HAND: all fingers extended
        if sum(fingers_up) >= 4:
            return "open_hand"

        return "neutral"

    # ──────────────────────────────────────────────────────────────────────────
    def _count_fingers(self, lm):
        """Returns list of 5 booleans [thumb, index, middle, ring, pinky]."""
        tips  = [4, 8, 12, 16, 20]
        pips  = [3, 6, 10, 14, 18]
        up    = []
        # Thumb: compare x instead of y
        up.append(lm[tips[0]].x < lm[pips[0]].x)
        for i in range(1, 5):
            up.append(lm[tips[i]].y < lm[pips[i]].y)
        return up

    # ──────────────────────────────────────────────────────────────────────────
    def _wrist_rotation_angle(self, lm):
        """
        Estimate wrist rotation from index MCP vs pinky MCP slope.
        Returns angle in degrees; positive = rotated clockwise.
        """
        ix, iy = lm[5].x,  lm[5].y   # index MCP
        px, py = lm[17].x, lm[17].y  # pinky MCP
        dx = px - ix
        dy = py - iy
        angle = math.degrees(math.atan2(dy, dx))
        return angle

    # ──────────────────────────────────────────────────────────────────────────
    def draw_landmarks(self, frame_rgb, hand_data):
        """Draw skeleton + gesture label onto frame (for webcam preview)."""
        import mediapipe as mp
        import cv2

        mp_hands = mp.solutions.hands
        mp_draw  = mp.solutions.drawing_utils

        # Re-run to get native results for drawing (lightweight second pass
        # is avoided by caching — for POC simplicity we use annotated frame)
        results = self.hands.process(frame_rgb)
        if results.multi_hand_landmarks:
            for hand_lm in results.multi_hand_landmarks:
                mp_draw.draw_landmarks(
                    frame_rgb, hand_lm, mp_hands.HAND_CONNECTIONS,
                    mp_draw.DrawingSpec(color=(0, 240, 180), thickness=2, circle_radius=4),
                    mp_draw.DrawingSpec(color=(255, 255, 255), thickness=1),
                )

        if hand_data and hand_data.get("gesture"):
            cv2.putText(
                frame_rgb,
                f"Gesture: {hand_data['gesture']}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (0, 240, 180), 2, cv2.LINE_AA
            )
            cv2.putText(
                frame_rgb,
                f"ROM: {hand_data['rom_degrees']:.1f} deg",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (255, 200, 50), 2, cv2.LINE_AA
            )

        return frame_rgb

    # ──────────────────────────────────────────────────────────────────────────
    def close(self):
        self.hands.close()
