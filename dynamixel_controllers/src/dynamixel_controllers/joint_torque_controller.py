# -*- coding: utf-8 -*-
#
# Software License Agreement (BSD License)
#
# Copyright (c) 2010-2011, Antons Rebguns.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of University of Arizona nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from __future__ import division


__author__ = 'Antons Rebguns'
__copyright__ = 'Copyright (c) 2010-2011 Antons Rebguns'
__credits__ = 'Cody Jorgensen'

__license__ = 'BSD'
__maintainer__ = 'Antons Rebguns'
__email__ = 'anton@email.arizona.edu'


import roslib
roslib.load_manifest('dynamixel_controllers')

import rospy
from dynamixel_driver.dynamixel_const import *
from dynamixel_driver.dynamixel_ros_commands import *
from dynamixel_controllers.joint_controller import JointController

from ua_controller_msgs.msg import JointState
from std_msgs.msg import Float64

class JointTorqueController(JointController):
    def __init__(self, out_cb, param_path, port_name):
        JointController.__init__(self, out_cb, param_path, port_name)
        
        self.motor_id = rospy.get_param(self.topic_name + '/motor/id')
        self.initial_position_raw = rospy.get_param(self.topic_name + '/motor/init')
        self.min_angle_raw = rospy.get_param(self.topic_name + '/motor/min')
        self.max_angle_raw = rospy.get_param(self.topic_name + '/motor/max')
        
        self.flipped = self.min_angle_raw > self.max_angle_raw
        self.last_commanded_torque = 0.0
        
        self.joint_state = JointState(name=self.joint_name, motor_ids=[self.motor_id])

    def initialize(self):
        # verify that the expected motor is connected and responding
        available_ids = rospy.get_param('dynamixel/%s/connected_ids' % self.port_namespace, [])
        
        if not self.motor_id in available_ids:
            rospy.logwarn('The specified motor id is not connected and responding.')
            rospy.logwarn('Available ids: %s' % str(available_ids))
            rospy.logwarn('Specified id: %d' % self.motor_id)
            return False
            
        self.radians_per_encoder_tick = rospy.get_param('dynamixel/%s/%d/radians_per_encoder_tick' % (self.port_namespace, self.motor_id))
        self.encoder_ticks_per_radian = rospy.get_param('dynamixel/%s/%d/encoder_ticks_per_radian' % (self.port_namespace, self.motor_id))
        
        if self.flipped:
            self.min_angle = (self.initial_position_raw - self.min_angle_raw) * self.radians_per_encoder_tick
            self.max_angle = (self.initial_position_raw - self.max_angle_raw) * self.radians_per_encoder_tick
        else:
            self.min_angle = (self.min_angle_raw - self.initial_position_raw) * self.radians_per_encoder_tick
            self.max_angle = (self.max_angle_raw - self.initial_position_raw) * self.radians_per_encoder_tick
            
        self.encoder_resolution = rospy.get_param('dynamixel/%s/%d/encoder_resolution' % (self.port_namespace, self.motor_id))
        self.max_position = self.encoder_resolution - 1
        self.set_speed(0.0)
        
        if self.compliance_slope is not None: self.set_compliance_slope(self.compliance_slope)
        if self.compliance_margin is not None: self.set_compliance_margin(self.compliance_margin)
        if self.compliance_punch is not None: self.set_compliance_punch(self.compliance_punch)
        if self.torque_limit is not None: self.set_torque_limit(self.torque_limit)
        return True

    def set_torque_enable(self, torque_enable):
        mcv = (self.motor_id, torque_enable)
        self.send_packet_callback((DXL_SET_TORQUE_ENABLE, [mcv]))

    def set_speed(self, speed):
        if speed < -self.joint_max_speed: speed = -self.joint_max_speed
        elif speed > self.joint_max_speed: speed = self.joint_max_speed
        self.last_commanded_torque = speed
        speed_raw = int(round(speed / DXL_SPEED_RAD_SEC_PER_TICK))
        mcv = (self.motor_id, speed_raw)
        self.send_packet_callback((DXL_SET_GOAL_SPEED, [mcv]))

    def set_compliance_slope(self, slope):
        if slope < DXL_MIN_COMPLIANCE_SLOPE: slope = DXL_MIN_COMPLIANCE_SLOPE
        elif slope > DXL_MAX_COMPLIANCE_SLOPE: slope = DXL_MAX_COMPLIANCE_SLOPE
        slope2 = (slope << 8) + slope
        mcv = (self.motor_id, slope2)
        self.send_packet_callback((DXL_SET_COMPLIANCE_SLOPES, [mcv]))

    def set_compliance_margin(self, margin):
        if margin < DXL_MIN_COMPLIANCE_MARGIN: margin = DXL_MIN_COMPLIANCE_MARGIN
        elif margin > DXL_MAX_COMPLIANCE_MARGIN: margin = DXL_MAX_COMPLIANCE_MARGIN
        else: margin = int(margin)
        margin2 = (margin << 8) + margin    # pack margin_cw and margin_ccw into 2 bytes
        mcv = (self.motor_id, margin2)
        self.send_packet_callback((DXL_SET_COMPLIANCE_MARGINS, [mcv]))

    def set_compliance_punch(self, punch):
        if punch < DXL_MIN_PUNCH: punch = DXL_MIN_PUNCH
        elif punch > DXL_MAX_PUNCH: punch = DXL_MAX_PUNCH
        else: punch = int(punch)
        mcv = (self.motor_id, punch)
        self.send_packet_callback((DXL_SET_PUNCH, [mcv]))

    def set_torque_limit(self, max_torque):
        if max_torque > 1: max_torque = 1.0         # use all torque motor can provide
        elif max_torque < 0: max_torque = 0.0       # turn off motor torque
        raw_torque_val = int(DXL_MAX_TORQUE_TICK * max_torque)
        mcv = (self.motor_id, raw_torque_val)
        self.send_packet_callback((DXL_SET_TORQUE_LIMIT, [mcv]))

    def process_motor_states(self, state_list):
        if self.running:
            state = filter(lambda state: state.id == self.motor_id, state_list.motor_states)
            if state:
                state = state[0]
                self.joint_state.motor_temps = [state.temperature]
                self.joint_state.goal_pos = self.last_commanded_torque
                self.joint_state.current_pos = self.raw_to_rad(state.position, self.initial_position_raw, self.flipped, self.radians_per_encoder_tick)
                self.joint_state.error = 0.0
                self.joint_state.velocity = (state.speed / DXL_MAX_SPEED_TICK) * DXL_MAX_SPEED_RAD
                self.joint_state.load = state.load
                self.joint_state.is_moving = state.moving
                self.joint_state.header.stamp = rospy.Time.from_sec(state.timestamp)
                
                self.joint_state_pub.publish(self.joint_state)

    def process_command(self, msg):
        self.set_speed(msg.data)

