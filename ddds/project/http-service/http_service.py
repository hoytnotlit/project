# -*- coding: utf-8 -*-
import json
from os import getenv

from flask import Flask, request
from jinja2 import Environment
from urllib.request import Request, urlopen
import structlog

from logger import configure_stdout_logging

from random import randrange

def setup_logger():
    logger = structlog.get_logger(__name__)
    try:
        log_level = getenv("LOG_LEVEL", default="INFO")
        configure_stdout_logging(log_level)
        return logger
    except BaseException:
        logger.exception("exception during logger setup")
        raise


logger = setup_logger()
app = Flask(__name__)
environment = Environment()


def jsonfilter(value):
    return json.dumps(value)


environment.filters["json"] = jsonfilter


def error_response(message):
    response_template = environment.from_string("""
    {
      "status": "error",
      "message": {{message|json}},
      "data": {
        "version": "1.0"
      }
    }
    """)
    payload = response_template.render(message=message)
    response = app.response_class(
        response=payload,
        status=200,
        mimetype='application/json'
    )
    logger.info("Sending error response to TDM", response=response)
    return response


def query_response(value, grammar_entry):
    response_template = environment.from_string("""
    {
      "status": "success",
      "data": {
        "version": "1.1",
        "result": [
          {
            "value": {{value|json}},
            "confidence": 1.0,
            "grammar_entry": {{grammar_entry|json}}
          }
        ]
      }
    }
    """)
    payload = response_template.render(
        value=value, grammar_entry=grammar_entry)
    response = app.response_class(
        response=payload,
        status=200,
        mimetype='application/json'
    )
    logger.info("Sending query response to TDM", response=response)
    return response


def multiple_query_response(results):
    response_template = environment.from_string("""
    {
      "status": "success",
      "data": {
        "version": "1.0",
        "result": [
        {% for result in results %}
          {
            "value": {{result.value|json}},
            "confidence": 1.0,
            "grammar_entry": {{result.grammar_entry|json}}
          }{{"," if not loop.last}}
        {% endfor %}
        ]
      }
    }
     """)
    payload = response_template.render(results=results)
    response = app.response_class(
        response=payload,
        status=200,
        mimetype='application/json'
    )
    logger.info("Sending multiple query response to TDM", response=response)
    return response


def validator_response(is_valid):
    response_template = environment.from_string("""
    {
      "status": "success",
      "data": {
        "version": "1.0",
        "is_valid": {{is_valid|json}}
      }
    }
    """)
    payload = response_template.render(is_valid=is_valid)
    response = app.response_class(
        response=payload,
        status=200,
        mimetype='application/json'
    )
    logger.info("Sending validator response to TDM", response=response)
    return response


@app.route("/dummy_query_response", methods=['POST'])
def dummy_query_response():
    response_template = environment.from_string("""
    {
      "status": "success",
      "data": {
        "version": "1.1",
        "result": [
          {
            "value": "dummy",
            "confidence": 1.0,
            "grammar_entry": null
          }
        ]
      }
    }
     """)
    payload = response_template.render()
    response = app.response_class(
        response=payload,
        status=200,
        mimetype='application/json'
    )
    logger.info("Sending dummy query response to TDM", response=response)
    return response


@app.route("/action_success_response", methods=['POST'])
def action_success_response():
    response_template = environment.from_string("""
   {
     "status": "success",
     "data": {
       "version": "1.1"
     }
   }
   """)
    payload = response_template.render()
    response = app.response_class(
        response=payload,
        status=200,
        mimetype='application/json'
    )
    logger.info("Sending successful action response to TDM", response=response)
    return response


def get_data(query, municipality=""):
    query = query.replace(" ", "%20")
    url = f"https://api.hel.fi/servicemap/v2/search/?language=en&q={query}&municipality={municipality}"
    print(url)
    request = Request(url)
    response = urlopen(request)
    data = response.read()
    return json.loads(data)


@app.route("/unit_contact", methods=['POST'])
def unit_contact():
    payload = request.get_json()
    unit_to_search = payload["context"]["facts"]["unit_to_search"]["grammar_entry"]
    data = get_data(unit_to_search)
    contact_type = payload["context"]["facts"]["contact_type"]["value"]
    result = data['results'][0][contact_type] if data['results'][0][contact_type] != None else "empty"
    return query_response(result, None)


@app.route("/find_service", methods=['POST'])
def find_service():
    payload = request.get_json()
    service_to_search = payload["context"]["facts"]["service_to_search"]["grammar_entry"]
    city_to_search = payload["context"]["facts"]["city_to_search"]["grammar_entry"]
    data = get_data(service_to_search, city_to_search)

    result = "empty"
    # check accessibility
    # NOTE I couldn't figure out how the API actually returns the accessibility so this functionality is faked
    if "accessibility_to_search" in payload["context"]["facts"]:
      accessibility_to_search = payload["context"]["facts"]["accessibility_to_search"]
      if accessibility_to_search["value"] == "wheelchair_accessible":
        data['results'] = [x for x in data['results'] if x['accessibility_viewpoints']]

    if len(data['results']) > 0:
      rand_index = randrange(len(data['results']))
      result = data['results'][rand_index]['name']['en'] 
      if payload["context"]["facts"]["want_address"]['value'] == "yes":
        result += ", " + data['results'][rand_index]['street_address']['en']

    value = "new_unit" if result != "empty" else "empty"
    return query_response(value, result)


@app.route("/get_accesibility", methods=['POST'])
def get_accesibility():
    payload = request.get_json()
    unit_to_search = payload["context"]["facts"]["unit_to_search"]["grammar_entry"]
    data = get_data(unit_to_search)
    response = "No it is not"
    if len(data['results']) < 1:
      response = "empty"
    # NOTE I couldn't figure out how the API actually returns the accessibility so this functionality is faked
    elif data['results'][0]['accessibility_viewpoints']:
        response = "Yes it is"
    return query_response(response, None)
