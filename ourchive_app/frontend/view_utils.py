from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, logout, login
from django.contrib import messages
from .search_models import SearchObject
from html import escape, unescape
from django.http import HttpResponse, FileResponse
import logging
from .api_utils import do_get, do_post, do_patch, do_delete, validate_captcha
from django.utils.translation import gettext as _
from api import utils
from django.views.decorators.cache import never_cache
from dateutil.parser import *
from dateutil import tz
from urllib.parse import unquote, quote
import random
from django.core.cache import cache
from django.views.decorators.vary import vary_on_cookie
from operator import itemgetter

def group_tags(tags):
	tag_parent = {}
	for tag in tags:
		if tag['tag_type'] not in tag_parent:
			tag_parent[tag['tag_type']] = [tag]
		else:
			tag_parent[tag['tag_type']].append(tag)
	return tag_parent


def group_tags_for_edit(tags, tag_types=None):
	tag_parent = {tag_type['label']:{'admin_administrated': tag_type['admin_administrated'], 'type_name': tag_type['type_name']} for tag_type in tag_types['results']}
	for tag in tags:
		tag['text'] = tag['text']
		if 'tags' not in tag_parent[tag['tag_type']]:
			tag_parent[tag['tag_type']]['tags'] = []
			tag_parent[tag['tag_type']]['tags'].append(tag)
		else:
			tag_parent[tag['tag_type']]['tags'].append(tag)
	return tag_parent


def process_attributes(obj_attrs, all_attrs):
	obj_attrs = [attribute['name'] for attribute in obj_attrs]
	for attribute in all_attrs:
		for attribute_value in attribute['attribute_values']:
			if attribute_value['name'] in obj_attrs:
				attribute_value['checked'] = True
	return all_attrs


def get_attributes_from_form_data(request):
	obj_attributes = []
	attributes = request.POST.getlist('attributevals')
	for attribute in attributes:
		attribute_vals = attribute.split('|_|')
		if len(attribute_vals) > 1:
			obj_attributes.append({
				"attribute_type": attribute_vals[0],
				"name": attribute_vals[1]
			})
	return obj_attributes


def get_attributes_for_display(obj_attrs):
	attrs = {}
	attr_types = set()
	for attribute in obj_attrs:
		if attribute['attribute_type'] not in attr_types:
			attr_types.add(attribute['attribute_type'])
			attrs[attribute['attribute_type']] = []
		attrs[attribute['attribute_type']].append(attribute['display_name'])
	return attrs


def get_array_attributes_for_display(dict_array, attr_key):
	for obj in dict_array:
		obj[attr_key] = get_attributes_for_display(obj[attr_key])
	return dict_array


def sanitize_rich_text(rich_text):
	if rich_text is not None:
		rich_text = escape(rich_text)
	else:
		rich_text = ''
	return rich_text


def get_work_obj(request, work_id=None):
	work_dict = request.POST.copy()
	publish_all = False
	if 'publish_all' in work_dict:
		publish = work_dict.pop('publish_all')
		if publish[0].lower() == 'on':
			publish_all = True
	if 'preferred_download_url' in work_dict and work_dict['preferred_download_url'] == 'None':
		work_dict['preferred_download_url'] = ''
	if 'preferred_download' in work_dict and work_dict['preferred_download'] == 'None':
		work_dict.pop('preferred_download')
	multichapter = work_dict.pop('multichapter') if 'multichapter' in work_dict else None
	chapter_dict = {
		'title': '',
		'summary': '',
		'notes': '',
		'number': '1',
		'image_url': '',
		'image_url-upload': '',
		'image_alt_text': '',
		'audio_url': '',
		'audio_url-upload': '',
		'audio_description': '',
		'text': '',
		'work': '',
		'draft': 'chapter_draft' in request.POST,
		'end_notes': ''
	}
	tags = []
	tag_types = {}
	chapters = []
	result = do_get(f'api/tagtypes', request)
	for item in result.response_data['results']:
		tag_types[item['type_name']] = item
	for item in request.POST:
		if item in chapter_dict and not multichapter:
			val_list = request.POST.getlist(item)
			if len(val_list) > 1:
				chapter_dict[item] = val_list[1]
				work_dict[item] = val_list[0]
			else:
				chapter_dict[item] = request.POST[item]
		elif item in chapter_dict:
			val_list = request.POST.getlist(item)
			if len(val_list) > 1:
				work_dict[item] = val_list[0]
		elif item == 'chapter_id':
			chapter_dict['id'] = request.POST[item]
			work_dict.pop('chapter_id')
		elif 'tags' in request.POST[item] and settings.TAG_DIVIDER in request.POST[item]:
			tag = {}
			json_item = request.POST[item].split(settings.TAG_DIVIDER)
			tag['tag_type'] = tag_types[json_item[2]]['label']
			tag['text'] = json_item[1]
			if not json_item[1].strip():
				continue
			tags.append(tag)
			work_dict.pop(item)
		elif 'chapters_' in item and work_id is not None:
			chapter_id = item[9:]
			chapter_number = request.POST[item]
			chapters.append({'id': chapter_id, 'number': chapter_number, 'work': work_id})
	work_dict["tags"] = tags
	chapter_dict = None if multichapter else chapter_dict
	if work_id and chapter_dict:
		chapter_dict['work'] = work_id
	if 'comments_permitted' not in work_dict:
		comments_permitted = False
	else:
		comments_permitted = work_dict["comments_permitted"]
		work_dict["comments_permitted"] = comments_permitted == "All" or comments_permitted == "Registered users only"
	work_dict["anon_comments_permitted"] = comments_permitted == "All"
	redirect_toc = work_dict.pop('redirect_toc')[0]
	work_dict["is_complete"] = "is_complete" in work_dict
	work_dict["draft"] = "work_draft" in work_dict
	work_dict = work_dict.dict()
	work_dict["user"] = str(request.user)
	work_dict["attributes"] = get_attributes_from_form_data(request)
	return [work_dict, redirect_toc, chapters, chapter_dict, publish_all]


def get_bookmark_obj(request):
	bookmark_dict = request.POST.copy()
	tags = []
	tag_types = {}
	result = do_get(f'api/tagtypes', request)
	for item in result.response_data['results']:
		tag_types[item['type_name']] = item
	for item in request.POST:
		if 'tags' in request.POST[item] and settings.TAG_DIVIDER in request.POST[item]:
			tag = {}
			json_item = request.POST[item].split(settings.TAG_DIVIDER)
			if not json_item[1].strip():
				continue
			tag['tag_type'] = tag_types[json_item[2]]['label']
			tag['text'] = json_item[1]
			tags.append(tag)
			bookmark_dict.pop(item)
	bookmark_dict["tags"] = tags
	comments_permitted = bookmark_dict["comments_permitted"]
	bookmark_dict["comments_permitted"] = comments_permitted == "All" or comments_permitted == "Registered users only"
	bookmark_dict["anon_comments_permitted"] = comments_permitted == "All"
	bookmark_dict = bookmark_dict.dict()
	bookmark_dict["user"] = str(request.user)
	bookmark_dict["draft"] = 'draft' in bookmark_dict
	bookmark_dict["attributes"] = get_attributes_from_form_data(request)
	return bookmark_dict


def get_bookmark_collection_obj(request):
	collection_dict = request.POST.copy()
	tags = []
	bookmarks = []
	tag_types = {}
	result = do_get(f'api/tagtypes', request)
	for item in result.response_data['results']:
		tag_types[item['type_name']] = item
	for item in request.POST:
		if 'tags' in request.POST[item] and settings.TAG_DIVIDER in request.POST[item]:
			tag = {}
			json_item = request.POST[item].split(settings.TAG_DIVIDER)
			tag['tag_type'] = tag_types[json_item[2]]['label']
			tag['text'] = json_item[1]
			if not json_item[1].strip():
				continue
			tags.append(tag)
			collection_dict.pop(item)
		if 'bookmarksidstoadd' in request.POST[item]:
			json_item = request.POST[item].split("_")
			if len(json_item) < 2:
				continue
			bookmark_id = json_item[1]
			bookmarks.append(bookmark_id)
			collection_dict.pop(item)
	collection_dict["tags"] = tags
	collection_dict["bookmarks"] = bookmarks
	comments_permitted = collection_dict["comments_permitted"]
	collection_dict["comments_permitted"] = comments_permitted == "All" or comments_permitted == "Registered users only"
	collection_dict["anon_comments_permitted"] = comments_permitted == "All"
	collection_dict = collection_dict.dict()
	collection_dict["user"] = str(request.user)
	collection_dict["draft"] = 'draft' in collection_dict
	collection_dict["is_private"] = False
	collection_dict["attributes"] = get_attributes_from_form_data(request)
	return collection_dict


def prepare_chapter_data(chapter, request):
	if 'text' in chapter:
		chapter['text'] = sanitize_rich_text(chapter['text'])
		chapter['text'] = chapter['text'].replace('\r\n', '<br/>')
	if 'summary' in chapter:
		chapter['summary'] = sanitize_rich_text(chapter['summary'])
	if 'notes' in chapter:
		chapter['notes'] = sanitize_rich_text(chapter['notes'])
		chapter['notes'] = chapter['notes'].replace('\r\n', '<br/>')
	if 'end_notes' in chapter:
		chapter['end_notes'] = sanitize_rich_text(chapter['end_notes'])
		chapter['notes'] = chapter['notes'].replace('\r\n', '<br/>')
	og_attributes = chapter['attributes'] if 'attributes' in chapter else []
	chapter_attributes = do_get(f'api/attributetypes', request, params={'allow_on_chapter': True}, object_name='Attribute')
	chapter['attribute_types'] = process_attributes(og_attributes, chapter_attributes.response_data['results'])
	return chapter


def get_bookmark_boilerplate(request, work_id):
	bookmark = {
			'title': '',
			'description': '',
			'user': request.user.username,
			'work': {'title': request.GET.get('title'), 'id': work_id},
			'anon_comments_permitted': True,
			'comments_permitted': True
		}
	bookmark_attributes = do_get(f'api/attributetypes', request, params={'allow_on_bookmark': True}, object_name='Attribute')
	bookmark['attribute_types'] = process_attributes([], bookmark_attributes.response_data['results'])
	tag_types = do_get(f'api/tagtypes', request, 'Tag Type').response_data
	tags = group_tags_for_edit([], tag_types)
	# todo - this should be a specific endpoint, we don't need to retrieve 10 objects to get config
	star_count = do_get(f'api/bookmarks', request, 'Bookmark').response_data['star_count']
	bookmark['rating'] = star_count
	return [bookmark, tags, star_count]


# utility method to format date for the Django template engine.
# there should be a better way to do this. google was not forthcoming.
def format_date_for_template(obj, field_name, is_list=False):
	if not is_list and field_name not in obj:
		return obj
	if is_list:
		for item in obj:
			if field_name not in item:
				continue
			item[field_name] = parse(item[field_name]).date()
		return obj
	obj[field_name] = parse(obj[field_name]).date()
	return obj

def format_comments_for_template(comments):
	for comment in comments:
		comment = format_date_for_template(comment, 'updated_on')
		if comment['replies']:
			comment['replies'] = format_comments_for_template(comment['replies'])
	return comments

def referrer_redirect(request, alternate_url=None):
	response = None
	if request.META.get('HTTP_REFERER') is not None:
		if not any(loc in request.META['HTTP_REFERER'] for loc in ['/login', '/register', '/reset']):
			response = redirect(f"{request.META.get('HTTP_REFERER')}")
		else:
			refer = alternate_url if alternate_url is not None else '/'
			response = redirect(f"{refer}")
	else:
		response = redirect('/')
	return response


def get_object_tags(parent):
	for item in parent:
		item['tags'] = group_tags(item['tags']) if 'tags' in item else {}
	return parent


def get_unauthorized_message(request, redirect_url, html_tag):
	messages.add_message(request, messages.WARNING, _('You must log in to perform this action.'), html_tag)
	return redirect(redirect_url)


def process_message(request, response):
	message_type = messages.ERROR if response.response_info.status_code >= 400 else messages.SUCCESS
	messages.add_message(request, message_type, response.response_info.message, response.response_info.type_label)


def get_works_list(request, username=None):
	url = f'api/users/{username}/works' if username is not None else f'api/works'
	response = do_get(url, request, params=request.GET, object_name='User Works')
	if response.response_info.status_code >= 400:
		messages.add_message(request, messages.ERROR, response.response_info.message, response.response_info.type_label)
		return redirect('/')
	else:
		works = response.response_data['results']
		works = get_object_tags(works)
	return {'works': works, 'next_params': response.response_data['next_params'] if 'next_params' in response.response_data else None, 'prev_params': response.response_data['prev_params'] if 'prev_params' in response.response_data else None}
