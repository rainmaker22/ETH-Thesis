import numpy as np
import tensorflow as tf
from Config import *
from BasicModel import *

config = Config()

class Model(object):
	def __init__(self):
		# Parameters
		self.v_out_res        = config.V_OUT_RES
		self.v_out_nrow       = self.v_out_res[0]
		self.v_out_ncol       = self.v_out_res[1]
		self.res_num          = self.v_out_nrow * self.v_out_ncol

		# Vertex pool for prediction
		self.vertex_pool = []
		for i in range(self.v_out_nrow):
			for j in range(self.v_out_ncol):
				self.vertex_pool.append(np.zeros(self.v_out_res, dtype = np.float32))
				self.vertex_pool[-1][i, j] = 1.0
		self.vertex_pool.append(np.zeros(self.v_out_res, dtype = np.float32))
		self.vertex_pool = np.array(self.vertex_pool)

		self.num_stage = 3

		return

	def weightedLogLoss(self, gt, pred):
		num = tf.reduce_sum(tf.ones(tf.shape(gt)))
		n_pos = tf.reduce_sum(gt)
		n_neg = tf.reduce_sum(1 - gt)
		n_pos = tf.maximum(tf.minimum(n_pos, num - 1), 1)
		n_neg = tf.maximum(tf.minimum(n_neg, num - 1), 1)
		w = gt * num / n_pos + (1 - gt) * num / n_neg
		return tf.losses.log_loss(gt, pred, w / 2)

	def CNN(self, img, gt_boundary = None, gt_vertices = None, reuse = None):
		"""
			gt_boundary       : [batch_size, height, width, 1]
			gt_vertices       : [batch_size, height, width, 1]
		"""
		vgg_result = VGG19('VGG19', img, reuse = reuse)
		skip_feature = SkipFeature('SkipFeature', vgg_result, reuse = reuse)
		bb, vv = Mask('Mask_1', skip_feature, reuse = reuse)
		b_prob = [tf.nn.softmax(bb)[..., 0: 1]]
		v_prob = [tf.nn.softmax(bb)[..., 0: 1]]
		for i in range(2, self.num_stage + 1):
			stage_input = tf.concat([skip_feature, bb, vv], axis = -1)
			bb, vv = Mask('Mask_%d' % i, stage_input, reuse = reuse)
			b_prob.append(tf.nn.softmax(bb)[..., 0: 1])
			v_prob.append(tf.nn.softmax(vv)[..., 0: 1])
		if not reuse:
			loss_B, loss_V = 0, 0
			for item in b_prob:
				loss_B += self.weightedLogLoss(gt_boundary, item)
			for item in v_prob:
				loss_V += self.weightedLogLoss(gt_vertices, item)
			return skip_feature, b_prob[-1], v_prob[-1], loss_B, loss_V
		else:
			return skip_feature, b_prob[-1], v_prob[-1]

	def SIM(self, feature, sim_in, sim_in_idx, gt_sim_out = None, reuse = None):
		""" 
			feature    : [batch_size, height, width, num_channel]
			sim_in     : [num_pair, height, width, 1]
			sim_in_idx : [num_pair]
			gt_sim_out : [num_pair]
		"""
		feature_rep = tf.gather(feature, sim_in_idx)
		feature_cat = tf.concat([feature_rep, sim_in], axis = -1)
		prob = FC_SIM('SIM', feature_cat, reuse = reuse)
		if not reuse:
			loss = self.num_stage * self.weightedLogLoss(gt_sim_out, prob)
			return prob, loss
		else:
			return prob

	def train(self, aa, bb, vv, ii, dd, oo):
		#
		img           = tf.reshape(aa, [config.AREA_TRAIN_BATCH, config.AREA_SIZE[1], config.AREA_SIZE[0], 3])
		gt_boundary   = tf.reshape(bb, [config.AREA_TRAIN_BATCH, self.v_out_nrow, self.v_out_ncol, 1])
		gt_vertices   = tf.reshape(vv, [config.AREA_TRAIN_BATCH, self.v_out_nrow, self.v_out_ncol, 1])
		gt_sim_in     = tf.reshape(ii, [config.SIM_TRAIN_BATCH, self.v_out_nrow, self.v_out_ncol, 1])
		gt_sim_in_idx = tf.reshape(dd, [config.SIM_TRAIN_BATCH])
		gt_sim_out    = tf.reshape(oo, [config.SIM_TRAIN_BATCH])

		# CNN part
		_, pred_boundary, pred_vertices, loss_B, loss_V = self.CNN(img, gt_boundary, gt_vertices)
		# sim_feature = tf.concat([gt_boundary, gt_vertices], axis = -1)
		sim_feature = tf.concat([pred_boundary, pred_vertices], axis = -1)
		pred_sim, loss_SIM = self.SIM(sim_feature, gt_sim_in, gt_sim_in_idx, gt_sim_out)
		return loss_B, loss_V, loss_SIM, pred_boundary, pred_vertices, pred_sim

	def predict_mask(self, aa):
		img = tf.reshape(aa, [config.AREA_TEST_BATCH, config.AREA_SIZE[1], config.AREA_SIZE[0], 3])
		_, pred_boundary, pred_vertices = self.CNN(img, reuse = True)
		sim_feature = tf.concat([pred_boundary, pred_vertices], axis = -1)
		return sim_feature, pred_boundary, pred_vertices

	def predict_sim(self, ff, ii, dd):
		#
		feature       = tf.reshape(ff, [config.AREA_TEST_BATCH, self.v_out_nrow, self.v_out_ncol, 2])
		sim_in        = tf.reshape(ii, [-1, self.v_out_nrow, self.v_out_ncol, 1])
		sim_in_idx    = tf.reshape(dd, [-1])
		sim_prob      = self.SIM(feature, sim_in, sim_in_idx, reuse = True)
		return sim_prob

class Logger(object):
	def __init__(self, log_dir):
		self.writer = tf.summary.FileWriter(log_dir)
		return

	def log_scalar(self, tag, value, step):
		summary = tf.Summary(value = [tf.Summary.Value(tag = tag, simple_value = value)])
		self.writer.add_summary(summary, step)
		return

	def close(self):
		self.writer.close()
		return

