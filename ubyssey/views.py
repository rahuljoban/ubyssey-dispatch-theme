# Django imports
from django.shortcuts import render_to_response
from django.http import HttpResponse, Http404
from django.template import loader
from django.shortcuts import render, redirect
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Dispatch imports
from dispatch.apps.content.models import Article, Page, Section, Topic
from dispatch.apps.core.models import Person
from dispatch.apps.frontend.themes.default import DefaultTheme
from dispatch.apps.frontend.helpers import templates

# Ubyssey imports
from ubyssey.pages import Homepage
from ubyssey.helpers import ArticleHelper

# Python imports
from datetime import datetime
import json

class UbysseyTheme(DefaultTheme):

    SITE_TITLE = 'The Ubyssey'
    SITE_URL = settings.BASE_URL

    def get_article_meta(self, article):

        try:
            image = article.featured_image.image.get_medium_url()
        except:
            image = None

        return {
            'title': article.headline,
            'description': article.seo_description if article.seo_description is not None else article.snippet,
            'url': article.get_absolute_url,
            'image': image,
            'author': article.get_author_string()
        }


    def home(self, request):

        frontpage = ArticleHelper.get_frontpage(
            sections=('news', 'culture', 'opinion', 'sports', 'features', 'science'),
            max_days=7
        )

        frontpage_ids = [int(a.id) for a in frontpage[:2]]

        sections = ArticleHelper.get_frontpage_sections(exclude=frontpage_ids)

        try:
            articles = {
                'primary': frontpage[0],
                'secondary': frontpage[1],
                'thumbs': frontpage[2:4],
                'bullets': frontpage[4:6],
             }
        except IndexError:
            raise Exception('Not enough articles to populate the frontpage!')

        component_set = Homepage()

        popular = Article.objects.get_popular()[:5]

        blog = ArticleHelper.get_frontpage(section='blog', limit=5)

        title = "%s - UBC's official student newspaper" % self.SITE_TITLE

        context = {
            'title': title,
            'meta': {
                'title': title,
                'description': 'Weekly student newspaper of the University of British Columbia.',
                'url': self.SITE_URL
            },
            'title': "%s - UBC's official student newspaper" % self.SITE_TITLE,
            'articles': articles,
            'sections': sections,
            'popular': popular,
            'blog': blog,
            'components': component_set.components(),
            'day_of_week': datetime.now().weekday(),
        }
        return render(request, 'homepage/base.html', context)

    def article(self, request, section=None, slug=None):

        try:
            article = self.find_article(request, slug, section)
        except:
            raise Http404("Article could not be found.")

        article.add_view()

        ref = request.GET.get('ref', None)
        dur = request.GET.get('dur', None)

        authors_json = json.dumps([a.full_name for a in article.authors.all()])

        context = {
            'title': "%s - %s" % (article.headline, self.SITE_TITLE),
            'meta': self.get_article_meta(article),
            'article': article,
            'authors_json': authors_json,
            'reading_list': ArticleHelper.get_reading_list(article, ref=ref, dur=dur),
            'base_template': 'base.html'
        }

        t = loader.select_template(["%s/%s" % (article.section.slug, article.get_template()), article.get_template()])
        return HttpResponse(t.render(context))

    def article_ajax(self, request, pk=None):
        article = Article.objects.get(parent_id=pk, is_published=True)
        authors_json = json.dumps([a.full_name for a in article.authors.all()])

        context = {
            'article': article,
            'authors_json': authors_json,
            'base_template': 'blank.html'
        }

        data = {
            'id': article.parent_id,
            'headline': article.headline,
            'url': article.get_absolute_url(),
            'html': loader.render_to_string(article.get_template(), context)
        }

        return HttpResponse(json.dumps(data), content_type='application/json')

    def page(self, request, slug=None):

        try:
            page = self.find_page(request, slug)
        except:
            raise Http404("Page could not be found.")

        page.add_view()

        context = {
            'meta': {
                'title': page.title
            },
            'page': page
        }

        return render(request, 'page/base.html', context)

    def section(self, request, slug=None):

        try:
            section = Section.objects.get(slug=slug)
        except:
            return self.page(request, slug)

        articles = Article.objects.filter(section=section, is_published=True).order_by('-published_at')

        context = {
            'meta': {
                'title': section.name,
            },
            'section': section,
            'type': 'section',
            'articles': {
                'first': articles[0],
                'rest': articles[1:9]
            }
        }

        t = loader.select_template(["%s/%s" % (section.slug, 'section.html'), 'section.html'])
        return HttpResponse(t.render(context))

    def get_author_meta(self, person):

        return {
            'title': person.full_name,
            'image': person.get_image_url if person.image is not None else None,
        }

    def author(self, request, slug=None):

        try:
            person = Person.objects.get(slug=slug)
        except:
            raise Http404("Author could not be found.")

        articles = Article.objects.filter(authors=person, is_published=True)[:6]

        context = {
            'meta': self.get_author_meta(person),
            'person': person,
            'articles': articles
        }

        return render(request, 'author/base.html', context)

    def author_articles(self, request, slug=None):

        try:
            person = Person.objects.get(slug=slug)
        except:
            raise Http404("Author could not be found.")

        order = request.GET.get('order', 'newest')

        if order == 'newest':
            order_by = '-published_at'
        else:
            order_by = 'published_at'

        query = request.GET.get('q', False)

        article_list = Article.objects.filter(authors=person, is_published=True).order_by(order_by)

        if query:
            article_list = article_list.filter(headline__icontains=query)

        paginator = Paginator(article_list, 15) # Show 15 articles per page

        page = request.GET.get('page')

        try:
            articles = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            articles = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            articles = paginator.page(paginator.num_pages)

        context = {
            'meta': self.get_author_meta(person),
            'person': person,
            'articles': articles,
            'order': order,
            'q': query
        }

        return render(request, 'author/articles.html', context)

    def archive(self, request):

        years = ArticleHelper.get_years()

        sections = Section.objects.all()

        order = request.GET.get('order', 'newest')

        filters = []

        if order == 'oldest':
            filters.append('order=%s' % order)

        order_by = '-published_at' if order == 'newest' else 'published_at'

        context = {
            'sections': sections,
            'years': years,
            'order': order
        }

        query = request.GET.get('q', None)
        section_id = request.GET.get('section_id', None)

        year = request.GET.get('year', None)

        article_list = Article.objects.filter(is_published=True).order_by(order_by)

        if query == '':
            query = None

        if year is not None:
            context['year'] = int(year)
            article_list = article_list.filter(published_at__icontains=str(year))
            filters.append('year=%s' % year)

        if query is not None:
            article_list = article_list.filter(headline__icontains=query)
            context['q'] = query
            filters.append('q=%s' % query)

        if section_id is not None:
            article_list = article_list.filter(section = section_id)
            context['section_id'] = int(section_id)
            context['section_name'] = Section.objects.get(id=section_id)
            filters.append('section_id=%s' % section_id)

        if len(filters):
            query_string = '?' + '&'.join(filters)
        else:
            query_string = ''

        paginator = Paginator(article_list, 15) # Show 15 articles per page
        page = request.GET.get('page')

        try:
            articles = paginator.page(page)
        except PageNotAnInteger:
            articles = paginator.page(1)
        except EmptyPage:
            articles = paginator.page(paginator.num_pages)

        meta = {
            'title': 'Archive'
        }

        context['articles'] = articles
        context['count'] = paginator.count
        context['meta'] = meta
        context['query_string'] = query_string

        return render(request, 'archive.html', context)

    def search(self, request):

        return redirect(self.archive)

    def topic(self, request, pk=None):

        try:
            topic = Topic.objects.get(id=pk)
        except Topic.DoesNotExist:
            raise Http404("Topic does not exist.")

        articles = Article.objects.filter(topic=topic, is_published=True).order_by('-published_at')

        context = {
            'meta': {
                'title': topic.name
            },
            'section': topic,
            'type': 'topic',
            'articles': {
                'first': articles[0] if articles else None,
                'rest': articles[1:9]
            }
        }

        return render(request, 'section.html', context)

    def guide_index(self, request):

        context = {
        }

        return render(request, 'guide/index.html', context)


    def guide_article(self, request, slug=None):

        try:
            article = self.find_article(request, slug, 'guide')
        except:
            raise Http404('Article could not be found.')

        template_fields = article.get_template_fields()

        print template_fields

        try:
            next_a = self.find_article(request, template_fields['next_a'], 'guide')
        except:
            next_a = None

        try:
            next_b = self.find_article(request, template_fields['next_b'], 'guide')
        except:
            next_b = None

        article.add_view()

        context = {
            'title': article.headline,
            'meta': self.get_article_meta(article),
            'article': article,
            'next': [next_a, next_b]
        }

        return render(request, 'guide/article.html', context)
