class WorkSearch(object):
	def from_json(self, json_obj):
		self.id = json_obj["id"]
		self.title = json_obj["title"]
		self.summary = json_obj["summary"]
		self.notes = None if json_obj["notes"] == "null" else json_obj["notes"]
		self.is_complete = self.convert_bool(json_obj["is_complete"])
		self.process_status = None if json_obj["process_status"] == "null" else json_obj["process_status"]
		self.cover_url = None if json_obj["cover_url"] == "null" else json_obj["cover_url"]
		self.cover_alt_text = None if json_obj["cover_alt_text"] == "null" else json_obj["cover_alt_text"]
		self.epub_id = None if json_obj["epub_id"] == "null" else json_obj["epub_id"]
		self.zip_id = None if json_obj["zip_id"] == "null" else json_obj["zip_id"]
		self.anon_comments_permitted = self.convert_bool(json_obj["anon_comments_permitted"])
		self.comments_permitted = self.convert_bool(json_obj["comments_permitted"])
		self.word_count = json_obj["word_count"]
		self.audio_length = json_obj["audio_length"]
		self.user_id = json_obj["user_id"]
		self.work_type = None if json_obj["work_type"] == "null" else json_obj["work_type"]
		self.user = json_obj["user"]

	def convert_bool(string_bool):
		return False if string_bool == "false" else True


class SearchObject(object):
	def with_term(self, term, pagination=None, mode=('all', 'all'), order_by='-updated_on'):
		return_obj = {}
		work_search = {}
		work_search["term"] = term
		work_search["include_mode"] = mode[0]
		work_search["exclude_mode"] = mode[1]
		work_search["page"] = 1
		work_search["order_by"] = order_by
		work_search["include_filter"] = {'tags': [], 'attributes': []}
		work_search["exclude_filter"] = {'tags': [], 'attributes': []}
		return_obj["work_search"] = work_search

		bookmark_search = {}
		bookmark_search["term"] = term
		bookmark_search["page"] = 1
		bookmark_search["include_mode"] = mode[0]
		bookmark_search["exclude_mode"] = mode[1]
		bookmark_search["order_by"] = order_by
		bookmark_search["include_filter"] = {'tags': [], 'attributes': []}
		bookmark_search["exclude_filter"] = {'tags': [], 'attributes': []}
		return_obj["bookmark_search"] = bookmark_search

		collection_search = {}
		collection_search["term"] = term
		collection_search["include_mode"] = mode[0]
		collection_search["exclude_mode"] = mode[1]
		collection_search["page"] = 1
		collection_search["order_by"] = order_by
		collection_search["include_filter"] = {'tags': [], 'attributes': []}
		collection_search["exclude_filter"] = {'tags': [], 'attributes': []}
		return_obj["collection_search"] = collection_search

		user_search = {}
		user_search["term"] = term
		user_search["page"] = 1
		user_search["filter"] = {}
		return_obj["user_search"] = user_search

		tag_search = {}
		tag_search["term"] = term
		tag_search["include_mode"] = mode[0]
		tag_search["exclude_mode"] = mode[1]
		tag_search["page"] = 1
		tag_search["order_by"] = order_by
		tag_search["include_filter"] = {'tag_type': [], 'text': []}
		tag_search["exclude_filter"] = {'tag_type': [], 'text': []}
		return_obj["tag_search"] = tag_search

		if pagination:
			obj = pagination['obj'].lower()
			if obj == 'work':
				return_obj['work_search']['page'] = pagination['page']
			elif obj == 'bookmark':
				return_obj['bookmark_search']['page'] = pagination['page']
			elif obj == 'tag':
				return_obj['tag_search']['page'] = pagination['page']
			elif obj == 'bookmarkcollection':
				return_obj['collection_search']['page'] = pagination['page']

		return return_obj

	def get_object_type(self, filter_term):
		if 'audio' in filter_term:
			return 'work'
		elif 'tag_type' in filter_term:
			return 'tag'
		elif 'attribute_type' in filter_term:
			return 'attribute'
		elif 'work_type' in filter_term:
			return 'work'
		elif 'word_count' in filter_term:
			return 'work'
		elif 'complete' in filter_term:
			return 'work'
		elif 'rating' in filter_term:
			return 'bookmark'
