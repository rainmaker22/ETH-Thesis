import os, sys
import numpy as np
import tensorflow as tf
from Config import *
from Model import *
from RoadData import *
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import glob
import cv2
from PIL import Image
cmap = matplotlib.cm.get_cmap('viridis')

config = Config()

def savePNG(mat1, mat2, filename):
	if mat2.shape[0] < mat1.shape[0]:
		mat2 = cv2.resize(mat2, (0, 0), fx = 8, fy = 8, interpolation = cv2.INTER_NEAREST)
	if mat2.max() > 0:
		mat2 = mat2 / mat2.max()
	# plt.imshow(mat1)
	# plt.imshow(mat2, alpha = 0.5)
	# plt.axis('off')
	# plt.savefig(filename, bbox_inches = 'tight', pad_inches = 0)
	m1 = Image.fromarray(mat1, mode = 'RGB')
	m1.putalpha(255)
	m2 = Image.fromarray(np.array(cmap(mat2) * 255.0, np.uint8)).convert(mode = 'RGB')
	m2.putalpha(255)
	m2 = np.array(m2)
	m2[..., 3] = np.array(mat2 * 255.0, np.uint8)
	m2 = Image.fromarray(m2)
	Image.alpha_composite(m1, m2).save(filename)
	return

def preserve(filename, num_lines):
	f = open(filename, 'r')
	lines = f.readlines()
	f.close()
	f = open(filename, 'w')
	for line in lines:
		n = int(line.strip().split(',')[0].split()[-1])
		if n >= num_lines:
			break
		f.write(line)
	f.close()
	return

if __name__ == '__main__':
	assert(len(sys.argv) == 2 or len(sys.argv) == 3)
	a = [11, 20, 84, 95, 291, 300, 552, 559, 560, 563]

	# Define graph
	graph = Model(
		max_num_vertices = config.MAX_NUM_VERTICES,
		lstm_out_channel = config.LSTM_OUT_CHANNEL, 
		v_out_res = config.V_OUT_RES,
	)
	aa = tf.placeholder(tf.float32)
	bb = tf.placeholder(tf.float32)
	vv = tf.placeholder(tf.float32)
	ii = tf.placeholder(tf.float32)
	oo = tf.placeholder(tf.float32)
	tt = tf.placeholder(tf.float32)
	ee = tf.placeholder(tf.float32)
	ll = tf.placeholder(tf.int32)
	ff = tf.placeholder(tf.float32)
	dd = tf.placeholder(tf.int32)

	train_res = graph.train(aa, bb, vv, ii, oo, tt, ee, ll, dd)
	pred_mask_res = graph.predict_mask(aa)
	pred_path_res = graph.predict_path(ff, tt)
	# pred_path_res = graph.predict_path_tmp(ff, tt, [a[0], a[3], a[4], a[5], a[6], a[9], a[2], a[2], a[2]])

	# for v in tf.global_variables():
	# 	print(v.name)
	# quit()

	optimizer = tf.train.AdamOptimizer(learning_rate = config.LEARNING_RATE)
	train = optimizer.minimize(train_res[0] + train_res[1])
	saver = tf.train.Saver(max_to_keep = 5)
	init = tf.global_variables_initializer()

	city_name = sys.argv[1]
	mode = 'non-test'

	# Create new folder
	if not os.path.exists('./Model%s/' % city_name):
		os.makedirs('./Model%s/' % city_name)

	if not os.path.exists('./test_res%s/' % city_name):
		os.makedirs('./test_res%s/' % city_name)

	# Launch graph
	with tf.Session() as sess:
		# Create loggers
		train_writer = Logger('./Log/train/')
		valid_writer = Logger('./Log/valid/')
		choose_train = 0
		choose_valid = 0
		choose_test = -1

		# Restore weights
		if len(sys.argv) == 3:
			if sys.argv[2] == 'restore':
				print('Restore pre-trained weights.')
				files = glob.glob('./Model%s/Model-*.ckpt.meta' % city_name)
				files = [(int(file.replace('./Model%s/Model-' % city_name, '').replace('.ckpt.meta', '')), file) for file in files]
				files.sort()
				num, model_path = files[-1]
				saver.restore(sess, model_path.replace('.meta', ''))
				iter_obj = range(num + 1, config.NUM_ITER)
				preserve('./LossTrain.out', num + 1)
				preserve('./LossValid.out', num + 1)
				train_loss = open('./LossTrain.out', 'a')
				valid_loss = open('./LossValid.out', 'a')
			elif sys.argv[2] == 'test':
				print('Test mode. Restore pre-trained weights.')
				files = glob.glob('./Model%s/Model-*.ckpt.meta' % city_name)
				files = [(int(file.replace('./Model%s/Model-' % city_name, '').replace('.ckpt.meta', '')), file) for file in files]
				files.sort()
				num, model_path = files[-1]
				saver.restore(sess, model_path.replace('.meta', ''))
				iter_obj = range(50)
				choose_train = -1
				choose_valid = -1
				choose_test = 0
				mode = 'test'
		else:
			print('Initialize weights.')
			train_loss = open('./LossTrain.out', 'w')
			valid_loss = open('./LossValid.out', 'w')
			sess.run(init)
			iter_obj = range(config.NUM_ITER)

		# Main loop
		for i in iter_obj:
			# Get training batch data and create feed dictionary
			if i % 1 == choose_train:
				img, boundary, vertices, vertex_inputs, vertex_outputs, vertex_terminals, ends, seq_lens, path_idx = getDataBatch(config.AREA_TRAIN_BATCH, 'train')
				# for j in range(config.AREA_TRAIN_BATCH):
				# 	plt.imsave('0-img.png', img[j])
				# 	plt.imsave('1-b.png', boundary[j])
				# 	plt.imsave('2-v.png', vertices[j])
				# 	plt.imsave('3-s.png', vertex_terminals[j, 0, 0])
				# 	plt.imsave('3-t.png', vertex_terminals[j, 0, 1])
				# 	print('seq_len', seq_lens[j, 0])
				# 	for k in range(config.MAX_NUM_VERTICES):
				# 		plt.imsave('4-%d-vi.png'%k, vertex_inputs[j,0,k])
				# 		plt.imsave('4-%d-vo.png'%k, vertex_outputs[j,0,k])
				# 	print(ends[j,0])
				# print('press enter to continue')
				# input()
				# continue
				feed_dict = {
					aa: img, bb: boundary, vv: vertices, ii: vertex_inputs, oo: vertex_outputs, tt: vertex_terminals, ee: ends, ll: seq_lens, dd: path_idx
				}

				# Training and get result
				init_time = time.time()
				_, (loss_CNN, loss_RNN, pred_boundary, pred_vertices, pred_v_out, pred_end) = sess.run([train, train_res], feed_dict)
				cost_time = time.time() - init_time
				train_writer.log_scalar('Loss CNN'  , loss_CNN  , i)
				train_writer.log_scalar('Loss RNN'  , loss_RNN  , i)
				train_writer.log_scalar('Loss Full' , loss_CNN + loss_RNN, i)
				
				# Write loss to file
				train_loss.write('Train Iter %d, %.6lf, %.6lf, %.3lf\n' % (i, loss_CNN, loss_RNN, cost_time))
				train_loss.flush()

			# Validation
			if i % 100 == choose_valid:
				img, boundary, vertices, vertex_inputs, vertex_outputs, vertex_terminals, ends, seq_lens, path_idx = getDataBatch(config.AREA_TRAIN_BATCH, 'val')
				feed_dict = {
					aa: img, bb: boundary, vv: vertices, ii: vertex_inputs, oo: vertex_outputs, tt: vertex_terminals, ee: ends, ll: seq_lens, dd: path_idx
				}
				init_time = time.time()
				loss_CNN, loss_RNN, pred_boundary, pred_vertices, pred_v_out, pred_end = sess.run(train_res, feed_dict)
				cost_time = time.time() - init_time
				valid_writer.log_scalar('Loss CNN'  , loss_CNN  , i)
				valid_writer.log_scalar('Loss RNN'  , loss_RNN  , i)
				valid_writer.log_scalar('Loss Full' , loss_CNN + loss_RNN, i)
				valid_loss.write('Valid Iter %d, %.6lf, %.6lf, %.3lf\n' % (i, loss_CNN, loss_RNN, cost_time))
				valid_loss.flush()

			# Test
			if i % 1 == choose_test:
				img, _, _, _, _, _, _, _, _ = getDataBatch(1, 'val')
				# if i < 45 or i > 45:
				# 	continue
				print(i)
				feature, pred_boundary, pred_vertices = sess.run(pred_mask_res, feed_dict = {aa: img})

				path = 'test_res%s/' % city_name
				savePNG(img[0], np.zeros(config.AREA_SIZE), path + '%d-0.png' % i)
				savePNG(img[0], pred_boundary[0, ..., 0] * 255, path + '%d-1.png' % i)
				savePNG(img[0], pred_vertices[0, ..., 0] * 255, path + '%d-2.png' % i)

				map_b, map_v, all_terminal, indices = getAllTerminal(pred_boundary[0], pred_vertices[0])
				feature = np.concatenate([feature, map_b[np.newaxis, ..., np.newaxis], map_v[np.newaxis, ..., np.newaxis]], axis = -1)

				savePNG(img[0], map_b, path + '%d-3.png' % i)
				savePNG(img[0], map_v, path + '%d-4.png' % i)

				multi_roads = []
				prob_res_li = []
				for terminal_1, terminal_2 in all_terminal:
					pred_v_out_1, prob_res_1, rnn_prob_1 = sess.run(pred_path_res, feed_dict = {ff: feature, tt: terminal_1})
					pred_v_out_2, prob_res_2, rnn_prob_2 = sess.run(pred_path_res, feed_dict = {ff: feature, tt: terminal_2})
					if rnn_prob_1[0] >= rnn_prob_2[0]:
						multi_roads.append(pred_v_out_1[0])
						prob_res_li.append(prob_res_1[0])
					else:
						multi_roads.append(pred_v_out_2[0])
						prob_res_li.append(prob_res_2[0])

				paths, pathImgs = recoverMultiPath(img[0].shape[0: 2], multi_roads)
				paths[paths > 1e-3] = 1.0
				savePNG(img[0], paths, path + '%d-5.png' % i)
				os.makedirs('./test_res%s/%d' % (city_name, i))
				for j, pathImg in enumerate(pathImgs):
					savePNG(img[0], pathImg, path + '%d/%d-%d.png' % ((i,) + indices[j]))
					np.save(path + '%d/%d-%d.npy' % ((i,) + indices[j]), prob_res_li[j])

			# Save model
			if i % 10000 == choose_train:
				saver.save(sess, './Model%s/Model-%d.ckpt' % (city_name, i))

		if mode != 'test':
			# End main loop
			train_writer.close()
			valid_writer.close()
			train_loss.close()
			valid_loss.close()
