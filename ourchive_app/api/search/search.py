from api.models import Work, Tag, User, Chapter, TagType, WorkType, Bookmark, BookmarkComment, BookmarkCollection, ChapterComment, Message, NotificationType, Notification, OurchiveSetting
from api import object_factory
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
import json
import re
from django.db.models import Q
from .search_obj import WorkSearch, BookmarkSearch, TagSearch, UserSearch, CollectionSearch
from django.contrib.postgres.search import TrigramDistance, TrigramWordDistance
from api.utils import get_star_count
from django.core.paginator import Paginator
from django.conf import settings


class ElasticSearchProvider:
    from elasticsearch import Elasticsearch
    from elasticsearch_dsl import Search, Q

    def init_provider():
        print('init provider')

    def search_works(self, **kwargs):
        q = Q("multi_match", query=kwargs['filter']['term'], fields=[
              'title', 'summary', 'chapter__title', 'chapters__summary', 'tags__text'])
        filters = kwargs['filter']

        client = Elasticsearch()

        s = Search(using=client, index="work")
        if 'complete' in filters:
            s = s.filter("term", is_complete=True)
        if 'audio_length' in filters:
            s = s.filter("range", chapters__audio_length={
                "gt": filters['audio_length']
            })
        if 'image_formats' in filters:
            s = s.filter("terms", chapters__image_format=filters['image_formats'])
        if 'image_formats' in filters:
            s = s.filter("terms", tags__text_format=filters['tags'])
        s = s.query(q)
        response = s.execute()
        return response

    def search_bookmarks(self, **kwargs):
        print('search bookmarks')

    def search_users(self, **kwargs):
        print('search users')

    def search_tags(self, **kwargs):
        print('search users')


class ElasticSearchServiceBuilder:
    def __init__(self):
        self._instance = None

    def __call__(self, port, **_ignored):
        if not self._instance:
            self._instance = ElasticSearchProvider()
        return self._instance


class PostgresProvider:

    def init_provider():
        print('init provider')

    # ref: https://www.julienphalip.com/blog/adding-search-to-a-django-site-in-a-snap/
    def normalize_query(self, query_string,
                        findterms=re.compile(r'"([^"]+)"|(\S+)').findall,
                        normspace=re.compile(r'\s{2,}').sub):
        ''' Splits the query string in invidual keywords, getting rid of unecessary spaces
            and grouping quoted words together.
            Example:

            >>> normalize_query('  some random  words "with   quotes  " and   spaces')
            ['some', 'random', 'words', 'with quotes', 'and', 'spaces']

        '''
        return [normspace(' ', (t[0] or t[1]).strip()) for t in findterms(query_string)]

    def get_query(self, query_string, search_fields):
        ''' Returns a query, that is a combination of Q objects. That combination
            aims to search keywords within a model by testing the given search fields.

        '''
        query = None  # Query to search for every search term
        terms = self.normalize_query(query_string)
        for term in terms:
            or_query = None  # Query to search for a given term in each field
            for field_name in search_fields:
                q = Q(**{"%s__icontains" % field_name: term})
                if or_query is None:
                    or_query = q
                else:
                    or_query = or_query | q
            if query is None:
                query = or_query
            else:
                query = query & or_query
        return query

    def build_filter_query(self, filter_array, filter_text, existing_query):
        if len(filter_array) > 0:
            or_query = None
            for array_item in filter_array:
                q = Q(**{filter_text: array_item})
                if or_query is None:
                    or_query = q
                else:
                    or_query = or_query | q
            if existing_query is None:
                existing_query = or_query
            else:
                existing_query = existing_query | or_query
        return existing_query

    def build_range_query(self, filter_obj, existing_query):
        if len(filter_obj['ranges']) < 1:
            return existing_query
        or_query = None
        for array_item in filter_obj['ranges']:
            q_high = Q(**{filter_obj['less_than']: array_item[0]})
            q_low = Q(**{filter_obj['greater_than']: array_item[1]})
            if or_query is None:
                or_query = (q_high & q_low)
            else:
                or_query = or_query | (q_high & q_low)
        if existing_query is None:
            existing_query = or_query
        else:
            existing_query = existing_query | or_query
        print(existing_query)
        return existing_query

    def build_filters(self, filters, mode, include):
        full_filters = None
        for field in filters:
            join_filters = None
            if '_range' in field:
                join_filters = self.build_range_query(
                    filters[field], join_filters)
            else:
                for key in filters[field]:
                    join_filters = self.build_filter_query(
                        filters[field][key], key, join_filters)
            if join_filters:
                if not include:
                    join_filters = ~join_filters
                if full_filters is None:
                    full_filters = join_filters
                else:
                    if mode == "all":
                        full_filters = Q(full_filters & join_filters)
                    elif mode == "any":
                        full_filters = Q(full_filters | join_filters)
                    else:
                        full_filters = Q(full_filters & join_filters)
        return full_filters

    def process_results(self, resultset, page, obj):
        page_size = settings.REST_FRAMEWORK['PAGE_SIZE']
        paginator = Paginator(resultset, page_size)
        count = paginator.count if resultset else 0
        resultset = paginator.get_page(page) if resultset else []
        next_params = None if not resultset or not resultset.has_next(
        ) else f"/search/?limit={page_size}&page={page+1}&object_type={obj.__name__}"
        prev_params = None if not resultset or not resultset.has_previous(
        ) else f"/search/?limit={page_size}&page={page-1}&object_type={obj.__name__}"
        return [resultset, {"count": count, "prev_params": prev_params, "next_params": next_params}]

    def run_queries(self, filters, query, obj, trigram_fields, term, page=1, order_by='-updated_on', has_drafts=False, trigram_max=0.85, require_distinct=True, has_private=False):
        resultset = None
        page = int(page)
        # filter on query first, then use filters (more exact, used when searching within) to narrow
        if query is not None:
            resultset = obj.objects.filter(query)
        if filters is not None:
            if self.include_mode == "all" and filters[0]:
                for q_item in filters[0].children:
                    resultset = resultset.filter(q_item) if resultset else obj.objects.filter(q_item)
            else:
                if not resultset and filters[0]:
                    resultset = obj.objects.filter(filters[0]) 
                elif filters[0]:
                    resultset = resultset.filter(filters[0]) 
            if self.exclude_mode == "any" and filters[1]:
                for q_item in filters[1].children:
                    resultset = resultset.filter(~Q(q_item)) if resultset else obj.objects.filter(q_item)
            else:
                if not resultset and filters[1]:
                    resultset = obj.objects.filter(filters[1]) 
                elif filters[1]:
                    resultset = resultset.filter(filters[1]) 
        if resultset is not None and has_drafts:
            resultset = resultset.filter(draft=False)
        if resultset is not None and has_private:
            resultset = resultset.filter(is_private=False)
        if resultset is not None and len(resultset) == 0 and query:
            # if exact matching & filtering produced no results, let's do limited trigram searching
            if len(trigram_fields) > 1:
                resultset = obj.objects.annotate(zero_distance=TrigramWordDistance(
                    term, trigram_fields[0])).annotate(one_distance=TrigramWordDistance(term, trigram_fields[1]))
                if filters[0] and filters[1]:
                    resultset = resultset.filter(
                        Q((Q(zero_distance__lte=trigram_max) | Q(one_distance__lte=trigram_max)) & filters[0] & filters[1]))
                elif filters[0]:
                    resultset = resultset.filter(
                        Q((Q(zero_distance__lte=trigram_max) | Q(one_distance__lte=trigram_max)) & filters[0]))
                elif filters[1]:
                    resultset = resultset.filter(
                        Q((Q(zero_distance__lte=trigram_max) | Q(one_distance__lte=trigram_max)) & filters[1]))
                else:
                    resultset = resultset.filter(zero_distance__lte=trigram_max).filter(
                        one_distance__lte=trigram_max)
                if resultset is not None and has_drafts:
                    resultset = resultset.filter(draft=False)
                resultset = resultset.order_by(
                    'zero_distance', 'one_distance', order_by)
            else:
                resultset = obj.objects.annotate(
                    zero_distance=TrigramWordDistance(term, trigram_fields[0]))
                if filters[0] and filters[1]:
                    resultset = resultset.filter(
                        Q((Q(zero_distance__lte=trigram_max) & filters[0] & filters[1])))
                elif filters[0]:
                    resultset = resultset.filter(
                        Q((Q(zero_distance__lte=trigram_max) & filters[0])))
                elif filters[1]:
                    resultset = resultset.filter(
                        Q((Q(zero_distance__lte=trigram_max) & filters[1])))
                else:
                    resultset = resultset.filter(zero_distance__lte=trigram_max)
                if resultset is not None and has_drafts:
                    resultset = resultset.filter(draft=False)
                resultset = resultset.order_by('zero_distance', order_by)
            require_distinct = False
        if require_distinct and resultset:
            # remove any dupes & apply order_by
            resultset = resultset.order_by(order_by).distinct()
        return self.process_results(resultset, page, obj)

    def get_filters(self, search_object):
        final_filters = None
        include_filters = self.build_filters(
            search_object.filter.include_filters, search_object.include_mode, True)
        exclude_filters = self.build_filters(
            search_object.filter.exclude_filters, search_object.exclude_mode, False)
        return [include_filters, exclude_filters]

    def build_work_resultset(self, resultset, reserved_fields):
        # build final resultset
        result_json = []
        for result in resultset:
            chapters = list(result.chapters.all())
            username = result.user.username
            tags = []
            for tag in result.tags.all():
                tag_dict = {}
                tag_dict["tag_type"] = tag.tag_type.label
                tag_dict["text"] = tag.text
                tag_dict["display_text"] = tag.display_text
                tag_dict["id"] = tag.id
                tags.append(tag_dict)
            attributes = []
            for attribute in result.attributes.all():
                attribute_dict = {}
                attribute_dict["attribute_type"] = attribute.attribute_type.display_name
                attribute_dict["name"] = attribute.name
                attribute_dict["display_name"] = attribute.display_name
                attribute_dict["id"] = attribute.id
                attribute_dict["order"] = attribute.order
                attributes.append(attribute_dict)
            work_type = None if result.work_type is None else result.work_type.type_name
            result_dict = result.__dict__
            for field in reserved_fields:
                result_dict.pop(field, None)
            result_dict["user"] = username
            result_dict["work_type_name"] = work_type
            result_dict["tags"] = tags
            result_dict["attributes"] = attributes
            result_dict["chapter_count"] = len(chapters)
            result_json.append(result_dict)
        return result_json

    def build_bookmark_resultset(self, resultset, reserved_fields):
        result_json = []
        for result in resultset:
            username = result.user.username
            tags = []
            for tag in result.tags.all():
                tag_dict = {}
                tag_dict["tag_type"] = tag.tag_type.label
                tag_dict["text"] = tag.text
                tag_dict["display_text"] = tag.display_text
                tag_dict["id"] = tag.id
                tags.append(tag_dict)
            attributes = []
            for attribute in result.attributes.all():
                attribute_dict = {}
                attribute_dict["attribute_type"] = attribute.attribute_type.display_name
                attribute_dict["name"] = attribute.name
                attribute_dict["display_name"] = attribute.display_name
                attribute_dict["id"] = attribute.id
                attribute_dict["order"] = attribute.order
                attributes.append(attribute_dict)
            result_dict = result.__dict__
            result_dict["tags"] = tags
            result_dict["user"] = username
            result_dict["attributes"] = attributes
            result_dict["work"] = {}
            result_dict["work"]["id"] = result.work.id
            result_dict["work"]["title"] = result.work.title
            result_dict["work"]["user_id"] = result.work.user_id
            for field in reserved_fields:
                result_dict.pop(field, None)
            result_json.append(result_dict)
        return result_json

    def build_collection_resultset(self, resultset, reserved_fields):
        result_json = []
        for result in resultset:
            username = result.user.username
            tags = []
            for tag in result.tags.all():
                tag_dict = {}
                tag_dict["tag_type"] = tag.tag_type.label
                tag_dict["text"] = tag.text
                tag_dict["display_text"] = tag.display_text
                tag_dict["id"] = tag.id
                tags.append(tag_dict)
            attributes = []
            for attribute in result.attributes.all():
                attribute_dict = {}
                attribute_dict["attribute_type"] = attribute.attribute_type.display_name
                attribute_dict["name"] = attribute.name
                attribute_dict["display_name"] = attribute.display_name
                attribute_dict["id"] = attribute.id
                attribute_dict["order"] = attribute.order
                attributes.append(attribute_dict)
            result_dict = result.__dict__
            result_dict["tags"] = tags
            result_dict["attributes"] = attributes
            result_dict["user"] = username
            for field in reserved_fields:
                result_dict.pop(field, None)
            result_json.append(result_dict)
        return result_json

    def search_works(self, **kwargs):
        work_search = WorkSearch()
        work_search.from_dict(kwargs)
        work_filters = self.get_filters(work_search)
        # TODO: this is global - shouldn't really be here
        self.include_mode = work_search.include_mode
        self.exclude_mode = work_search.exclude_mode
        # build query
        query = self.get_query(work_search.term, work_search.term_search_fields)
        if not query and not work_filters:
            return {'data': []}
        resultset = self.run_queries(work_filters, query, Work, [
                                     'title', 'summary'], work_search.term, kwargs['page'], work_search.order_by, True)
        result_json = self.build_work_resultset(resultset[0], work_search.reserved_fields)
        return {'data': result_json, 'page': resultset[1]}

    def search_bookmarks(self, **kwargs):
        bookmark_search = BookmarkSearch()
        bookmark_search.from_dict(kwargs)
        bookmark_filters = self.get_filters(bookmark_search)
        query = self.get_query(bookmark_search.term, bookmark_search.term_search_fields)
        if not query and not bookmark_filters:
            return {'data': []}
        resultset = self.run_queries(bookmark_filters, query, Bookmark, [
                                     'title', 'description'], bookmark_search.term, kwargs.get('page', 1), bookmark_search.order_by, True, .85, True, True)
        result_json = self.build_bookmark_resultset(resultset[0], bookmark_search.reserved_fields)
        return {'data': result_json, 'page': resultset[1]}

    def search_collections(self, **kwargs):
        collection_search = CollectionSearch()
        collection_search.from_dict(kwargs)
        collection_filters = self.get_filters(collection_search)
        query = self.get_query(collection_search.term,
                               collection_search.term_search_fields)
        if not query and not collection_filters:
            return {'data': []}
        resultset = self.run_queries(collection_filters, query, BookmarkCollection, [
                                     'title', 'short_description'], collection_search.term, kwargs.get('page', 1), collection_search.order_by, True)
        result_json = self.build_collection_resultset(resultset[0], collection_search.reserved_fields)
        return {'data': result_json, 'page': resultset[1]}

    def search_users(self, **kwargs):
        user_search = UserSearch()
        user_search.from_dict(kwargs)
        query = self.get_query(user_search.term, user_search.term_search_fields)
        if query is None:
            return {'data': []}
        resultset = User.objects.filter(is_active=True).filter(query)[:20]
        result_json = []
        for result in resultset:
            result_dict = result.__dict__
            for field in user_search.reserved_fields:
                result_dict.pop(field, None)
            result_json.append(result_dict)
        return {'data': result_json, 'page': {}}

    def autocomplete_tags(self, term, tag_type, fetch_all=False):
        results = []
        resultset = None
        term = term.lower()
        if tag_type:
            resultset = Tag.objects.filter(
                tag_type__type_name=tag_type).filter(Q(text__icontains=term) | Q(display_text__icontains=term))
        else:
            resultset = Tag.objects.annotate(zero_distance=TrigramWordDistance(term, 'text'))
            resultset = resultset.filter(zero_distance__lte=.85)
            resultset = resultset.order_by('zero_distance', 'text')
            resultset = resultset[:10]
        if resultset is None:
            resultset = Tag.objects.filter(
                tag_type__type_name=tag_type) if fetch_all else []
        for result in resultset:
            results.append({"tag": result.text, "display_text": result.display_text,
                            "id": result.id, "type": result.tag_type.label, "type_name": result.tag_type.type_name})
        return results

    def autocomplete_bookmarks(self, term, user):
        results = []
        resultset = None
        term = term.lower()
        resultset = Bookmark.objects.filter(user__id=user,draft=False).filter(
            Q(title__icontains=term) | Q(work__title__icontains=term)).prefetch_related('work')
        for result in resultset:
            work_dict = vars(result.work)
            if '_state' in work_dict:
                work_dict.pop('_state')
            bookmark_dict = vars(result)
            if '_state' in bookmark_dict:
                bookmark_dict.pop('_state')
            bookmark_dict['work'] = work_dict
            results.append({"bookmark": bookmark_dict})
        return results

    def search_tags(self, **kwargs):
        tag_search = TagSearch()
        tag_search.from_dict(kwargs)
        tag_filters = self.get_filters(tag_search)
        query = self.get_query(tag_search.term, tag_search.term_search_fields)
        if not query and not tag_filters:
            return {'data': []}
        resultset = self.run_queries(tag_filters, query, Tag, [
                                     'text'], tag_search.term, kwargs.get('page', 1), tag_search.order_by, False, 0.7, False)
        result_json = []
        if resultset is None:
            return result_json
        for result in resultset[0]:
            tag_type = result.tag_type.label
            result_dict = result.__dict__
            for field in tag_search.reserved_fields:
                result_dict.pop(field, None)
            result_dict['tag_type'] = tag_type
            result_json.append(result_dict)
        return {'data': result_json, 'page': resultset[1]}

    def filter_by_tag(self, **kwargs):
        tag_search = TagSearch()
        work_search = WorkSearch()
        work_search.from_dict(kwargs['work_search'])
        work_filters = self.get_filters(work_search)
        bookmark_search = BookmarkSearch()
        bookmark_search.from_dict(kwargs['bookmark_search'])
        bookmark_filters = self.get_filters(bookmark_search)
        collection_search = CollectionSearch()
        collection_search.from_dict(kwargs['collection_search'])
        collection_filters = self.get_filters(collection_search)

        page = kwargs['page'] if 'page' in kwargs else 1
        tag = Tag.objects.get(pk=kwargs['tag_id'])
        works = Work.objects.filter(tags__id__exact=tag.id)
        if work_filters[0]:
            works = works.filter(work_filters[0])
        if work_filters[1]:
            works = works.filter(work_filters[1])
        works = works.filter(draft=False).order_by('-updated_on').distinct()
        bookmarks = Bookmark.objects.filter(tags__id__exact=tag.id)
        if bookmark_filters[0]:
            bookmarks = bookmarks.filter(bookmark_filters[0])
        if bookmark_filters[1]:
            bookmarks = bookmarks.filter(bookmark_filters[1])
        bookmarks = bookmarks.filter(draft=False).order_by('-updated_on').distinct()
        collections = BookmarkCollection.objects.filter(tags__id__exact=tag.id)
        if collection_filters[0]:
            collections = collections.filter(collection_filters[0])
        if collection_filters[1]:
            collections = collections.filter(collection_filters[1])
        collections = collections.filter(draft=False).order_by('-updated_on').distinct()

        works_processed = self.process_results(works, page, Work)
        bookmarks_processed = self.process_results(bookmarks, page, Bookmark)
        collections_processed = self.process_results(collections, page, BookmarkCollection)

        # tag result object
        result_json = []
        tag_type = tag.tag_type.label
        result_dict = tag.__dict__
        for field in tag_search.reserved_fields:
            result_dict.pop(field, None)
        result_dict['tag_type'] = tag_type
        result_json.append(result_dict)
        tag_results = {'data': result_json, 'page': {'count': len(result_json)}}

        work_results = {'data': self.build_work_resultset(works_processed[0], work_search.reserved_fields), 'page': works_processed[1]}
        bookmark_results = {'data': self.build_bookmark_resultset(bookmarks_processed[0], bookmark_search.reserved_fields), 'page': bookmarks_processed[1]}
        collection_results = {'data': self.build_collection_resultset(collections_processed[0], collection_search.reserved_fields), 'page': collections_processed[1]}
        results = {}
        results['work'] = work_results
        results['bookmark'] = bookmark_results
        results['collection'] = collection_results
        results['tag'] = tag_results
        results['user'] = {'data': [], 'page': {}}
        return results


    def get_result_facets(self, results, tag_id=None):
        result_json = []
        work_types = WorkType.objects.all()
        work_types_list = []
        for work_type in work_types:
            work_types_list.append(
                {"label": work_type.type_name, "filter_val": "work_type$" + work_type.type_name})
        work_types_dict = {}
        work_types_dict["label"] = "Work Type"
        work_types_dict["values"] = work_types_list
        result_json.append(work_types_dict)

        # todo move to db setting
        word_count_dict = {}
        word_count_dict["label"] = "Work Word Count"
        word_count_dict["values"] = [{"label": "Under 20,000", "filter_val": "word_count_range|ranges|0|20000"},
                                     {"label": "20,000 - 50,000",
                                         "filter_val": "word_count_range|ranges|20000|50000"},
                                     {"label": "50,000 - 80,000",
                                         "filter_val": "word_count_range|ranges|50000|80000"},
                                     {"label": "80,000 - 100,000",
                                      "filter_val": "word_count_range|ranges|80000|100000"},
                                     {"label": "100,000+", "filter_val": "word_count_range|ranges|10000000|100000"}]
        result_json.append(word_count_dict)

        # todo move to db setting
        audio_length_dict = {}
        audio_length_dict["label"] = "Audio Length"
        audio_length_dict["values"] = [{"label": "Under 30:00", "filter_val": "audio_length_range|ranges|0|30"},
                                       {"label": "30:00 - 1:00:00",
                                           "filter_val": "audio_length_range|ranges|30|60"},
                                       {"label": "1:00:00 - 2:00:00",
                                           "filter_val": "audio_length_range|ranges|60|120"},
                                       {"label": "2:00:00 - 3:00:00",
                                        "filter_val": "audio_length_range|ranges|120|180"},
                                       {"label": "3:00:00+", "filter_val": "audio_length_range|ranges|20000|180"}]
        result_json.append(audio_length_dict)

        # todo move to db setting
        complete_dict = {}
        complete_dict["label"] = "Complete?"
        complete_dict["values"] = [{"label": "Complete", "filter_val": "complete$1"},
                                   {"label": "Work In Progress", "filter_val": "complete$0"}]
        result_json.append(complete_dict)

        # TODO: DRY
        tag_filter_name = None
        if tag_id:
            tag_filter = Tag.objects.filter(id=tag_id).first()
            if tag_filter:
                tag_filter_name = tag_filter.display_text
        tags_dict = {}
        for tag_type in TagType.objects.all():
            tags_dict[tag_type.label] = []
        for result in results['work']['data']:
            if len(result['tags']) > 0:
                for tag in result['tags']:
                    if tag['display_text'] not in tags_dict[tag['tag_type']]:
                        tags_dict[tag['tag_type']].append(tag['display_text'])
        for result in results['bookmark']['data']:
            if len(result['tags']) > 0:
                for tag in result['tags']:
                    if tag['display_text'] not in tags_dict[tag['tag_type']]:
                        tags_dict[tag['tag_type']].append(tag['display_text'])
        for result in results['collection']['data']:
            if len(result['tags']) > 0:
                for tag in result['tags']:
                    if tag['display_text'] not in tags_dict[tag['tag_type']]:
                        tags_dict[tag['tag_type']].append(tag['display_text'])
        for result in results['tag']['data']:
            if result['display_text'] not in tags_dict[result['tag_type']]:
                tags_dict[result['tag_type']].append(result['display_text'])
        for key in tags_dict:
            if len(tags_dict[key]) > 0:
                tag_filter_vals = []
                for val in tags_dict[key]:
                    checked_tag = False
                    if tag_id and tag_filter_name and tag_filter_name == val:
                        checked_tag = True
                    filter_val = "tag_type," + str(key) + "$tag_text," + val
                    tag_filter_vals.append({"label": val, "filter_val": filter_val, "checked": checked_tag})
                result_json.append({'label': key, 'values': tag_filter_vals})

        attributes_dict = {}
        for result in results['work']['data']:
            if len(result['attributes']) > 0:
                for attribute in result['attributes']:
                    if attribute['attribute_type'] not in attributes_dict:
                        attributes_dict[attribute['attribute_type']] = [attribute['display_name']]
                    elif attribute['display_name'] not in attributes_dict[attribute['attribute_type']]:
                        attributes_dict[attribute['attribute_type']].append(attribute['display_name'])
        for result in results['bookmark']['data']:
            if len(result['attributes']) > 0:
                for attribute in result['attributes']:
                    if attribute['attribute_type'] not in attributes_dict:
                        attributes_dict[attribute['attribute_type']] = [attribute['display_name']]
                    elif attribute['display_name'] not in attributes_dict[attribute['attribute_type']]:
                        attributes_dict[attribute['attribute_type']].append(attribute['display_name'])
        for result in results['collection']['data']:
            if len(result['attributes']) > 0:
                for attribute in result['attributes']:
                    if attribute['attribute_type'] not in attributes_dict:
                        attributes_dict[attribute['attribute_type']] = [attribute['display_name']]
                    elif attribute['display_name'] not in attributes_dict[attribute['attribute_type']]:
                        attributes_dict[attribute['attribute_type']].append(attribute['display_name'])
        for key in attributes_dict:
            if len(attributes_dict[key]) > 0:
                attribute_filter_vals = []
                for val in attributes_dict[key]:
                    filter_val = "attribute_type," + str(key) + "$attribute_text," + val
                    attribute_filter_vals.append({"label": val, "filter_val": filter_val})
                result_json.append({'label': key, 'values': attribute_filter_vals})

        stars = OurchiveSetting.objects.get(name='Rating Star Count')
        bookmark_rating_dict = {}
        bookmark_rating_dict["label"] = "Rating"
        bookmark_rating_dict["values"] = []
        stars = get_star_count(stars)
        for star in stars:
            bookmark_rating_dict["values"].append(
                {"label": f"{star}", "filter_val": f"rating_gte${star}"})
        result_json.append(bookmark_rating_dict)

        return result_json


class PostgresServiceBuilder:
    def __init__(self):
        self._instance = None

    def __call__(self, **_ignored):
        if not self._instance:
            self._instance = PostgresProvider()
        return self._instance


factory = object_factory.ObjectFactory()
factory.register_builder('ELASTICSEARCH', ElasticSearchServiceBuilder())
factory.register_builder('POSTGRES', PostgresServiceBuilder())
factory.register_builder('Default', PostgresServiceBuilder())
