"""
Registry data integration routes for Carbon IMS
Supports: Verra, Gold Standard, ACR, CAR
"""

from flask import Blueprint, render_template, request, jsonify
import requests
from routes.auth import login_required

registry_bp = Blueprint('registry', __name__)


@registry_bp.route('/registry-data')
@login_required
def registry_data():
    """Display registry data search page"""
    return render_template('registry_data.html')


@registry_bp.route('/api/registry/search', methods=['GET'])
@login_required
def search_registry():
    """Search a carbon credit registry for projects"""
    registry = request.args.get('registry', 'verra')
    search_type = request.args.get('type', 'id')
    query = request.args.get('query', '')

    if not query:
        return jsonify({'error': 'Search query is required'}), 400

    try:
        if registry == 'verra':
            results = search_verra(query, search_type)
        elif registry == 'goldstandard':
            results = search_goldstandard(query, search_type)
        elif registry == 'acr':
            results = search_acr(query, search_type)
        elif registry == 'car':
            results = search_car(query, search_type)
        else:
            return jsonify({'error': 'Unknown registry'}), 400

        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@registry_bp.route('/api/registry/project', methods=['GET'])
@login_required
def get_registry_project():
    """Get detailed project information from a registry"""
    registry = request.args.get('registry', 'verra')
    project_id = request.args.get('projectId', '')

    if not project_id:
        return jsonify({'error': 'Project ID is required'}), 400

    try:
        if registry == 'verra':
            project = get_verra_project(project_id)
        elif registry == 'goldstandard':
            project = get_goldstandard_project(project_id)
        elif registry == 'acr':
            project = get_acr_project(project_id)
        elif registry == 'car':
            project = get_car_project(project_id)
        else:
            return jsonify({'error': 'Unknown registry'}), 400

        return jsonify({'project': project})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Verra Registry Functions

def search_verra(query, search_type):
    """Search Verra VCS registry using POST API"""
    try:
        url = 'https://registry.verra.org/uiapi/resource/resource/search?$skip=0&$top=50&$count=true'

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        if search_type == 'id':
            payload = {
                "program": "VCS",
                "resourceIdentifier": query
            }
        else:
            payload = {
                "program": "VCS",
                "resourceName": query
            }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            results = []

            items = data.get('value', data) if isinstance(data, dict) else data
            if isinstance(items, dict):
                items = items.get('value', [])

            for item in items:
                results.append(extract_verra_fields(item))

            return results
        else:
            print(f"Verra API returned status {response.status_code}: {response.text[:200]}")
            return []
    except Exception as e:
        print(f"Verra search error: {e}")
        return []


def extract_verra_fields(item):
    """Extract all available fields from Verra API response"""
    project_id = str(item.get('resourceIdentifier', item.get('id', '')))
    return {
        'projectId': project_id,
        'name': item.get('resourceName', item.get('name', '')),
        'status': item.get('resourceStatus', item.get('status', '')),
        'program': item.get('program', 'VCS'),
        'country': item.get('country', item.get('countryName', '')),
        'region': item.get('region', item.get('regionName', '')),
        'projectType': item.get('projectType', item.get('type', '')),
        'methodology': item.get('methodology', item.get('protocolCategory', '')),
        'protocol': item.get('protocolCategory', item.get('protocol', '')),
        'sectorialScope': item.get('sectorialScope', item.get('sectoralScope', '')),
        'proponent': item.get('proponent', item.get('proponentName', '')),
        'developer': item.get('projectDeveloper', item.get('developer', '')),
        'creditsIssued': item.get('totalVintageQuantity', item.get('issuedCredits', 0)),
        'creditsRetired': item.get('totalRetiredQuantity', item.get('retiredCredits', 0)),
        'creditsAvailable': item.get('totalAvailableQuantity', item.get('availableCredits', 0)),
        'creditsCancelled': item.get('totalCancelledQuantity', 0),
        'estimatedAnnualReductions': item.get('estimatedAnnualEmissionReductions', item.get('annualEmissionReductions', '')),
        'creditingPeriodStart': item.get('creditingPeriodStartDate', item.get('creditStartDate', '')),
        'creditingPeriodEnd': item.get('creditingPeriodEndDate', item.get('creditEndDate', '')),
        'registrationDate': item.get('registrationDate', ''),
        'validationDate': item.get('validationDate', ''),
        'verificationDate': item.get('verificationDate', ''),
        'firstIssuanceDate': item.get('firstIssuanceDate', ''),
        'additionalCertifications': item.get('additionalCertifications', item.get('ccbStandards', '')),
        'corsia': item.get('corsiaEligible', item.get('corsia', '')),
        'sdgGoals': item.get('sdgGoals', item.get('sustainableDevelopmentGoals', '')),
        'description': item.get('description', item.get('projectDescription', '')),
        'registryUrl': f"https://registry.verra.org/app/projectDetail/VCS/{project_id}"
    }


def get_verra_project(project_id):
    """Get detailed Verra project information"""
    try:
        url = f'https://registry.verra.org/uiapi/resource/resource/search?$skip=0&$top=1&$count=true'

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        payload = {
            "program": "VCS",
            "resourceIdentifier": str(project_id)
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            items = data.get('value', []) if isinstance(data, dict) else data

            if items and len(items) > 0:
                return extract_verra_fields(items[0])
            else:
                return {'error': 'Project not found', 'projectId': project_id}
        else:
            return {'error': f'API returned status {response.status_code}', 'projectId': project_id}
    except Exception as e:
        return {'error': str(e), 'projectId': project_id}


# Gold Standard Registry Functions

def search_goldstandard(query, search_type):
    """Search Gold Standard registry"""
    try:
        url = f'https://registry.goldstandard.org/projects?q={query}&page=1'

        headers = {
            'Accept': 'application/json',
            'User-Agent': 'CarbonIMS/1.0'
        }

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            results = []

            items = data.get('data', [])
            for item in items:
                results.append({
                    'projectId': str(item.get('id', '')),
                    'name': item.get('name', ''),
                    'status': item.get('status', ''),
                    'country': item.get('country', {}).get('name', '') if isinstance(item.get('country'), dict) else '',
                    'type': item.get('type', {}).get('name', '') if isinstance(item.get('type'), dict) else '',
                    'creditsIssued': item.get('credits_issued', 0),
                    'registryUrl': f"https://registry.goldstandard.org/projects/details/{item.get('id', '')}"
                })

            return results
        else:
            return []
    except Exception as e:
        print(f"Gold Standard search error: {e}")
        return []


def get_goldstandard_project(project_id):
    """Get detailed Gold Standard project information"""
    try:
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'CarbonIMS/1.0'
        }

        api_url = f'https://registry.goldstandard.org/projects/{project_id}'
        response = requests.get(api_url, headers=headers, timeout=30)

        if response.status_code == 200:
            item = response.json()
            data = item.get('data', item)
            return {
                'projectId': str(data.get('id', '')),
                'name': data.get('name', ''),
                'status': data.get('status', ''),
                'country': data.get('country', {}).get('name', '') if isinstance(data.get('country'), dict) else '',
                'region': data.get('region', ''),
                'protocol': data.get('methodology', {}).get('name', '') if isinstance(data.get('methodology'), dict) else '',
                'type': data.get('type', {}).get('name', '') if isinstance(data.get('type'), dict) else '',
                'developer': data.get('developer', {}).get('name', '') if isinstance(data.get('developer'), dict) else '',
                'creditsIssued': data.get('credits_issued', 0),
                'creditsRetired': data.get('credits_retired', 0),
                'creditsAvailable': data.get('credits_available', 0),
                'creditingPeriodStart': data.get('crediting_period_start', ''),
                'creditingPeriodEnd': data.get('crediting_period_end', ''),
                'registrationDate': data.get('registration_date', ''),
                'description': data.get('description', '')
            }
        else:
            return {'error': 'Project not found'}
    except Exception as e:
        return {'error': str(e)}


# ACR Registry Functions

def search_acr(query, search_type):
    """Search American Carbon Registry"""
    try:
        results = [{
            'projectId': query,
            'name': f'Search "{query}" on ACR Registry',
            'status': 'See Registry',
            'developer': '',
            'protocol': '',
            'registryUrl': f'https://acr2.apx.com/myModule/rpt/myrpt.asp?r=111&TabName=Projects'
        }]
        return results
    except Exception as e:
        print(f"ACR search error: {e}")
        return []


def get_acr_project(project_id):
    """Get ACR project - redirect to registry"""
    return {
        'projectId': project_id,
        'name': 'View on ACR Registry',
        'status': 'See registry for details',
        'registryUrl': f'https://acr2.apx.com/myModule/rpt/myrpt.asp?r=111&TabName=Projects'
    }


# CAR Registry Functions

def search_car(query, search_type):
    """Search Climate Action Reserve"""
    try:
        results = [{
            'projectId': query,
            'name': f'Search "{query}" on CAR Registry',
            'status': 'See Registry',
            'developer': '',
            'protocol': '',
            'registryUrl': f'https://thereserve2.apx.com/myModule/rpt/myrpt.asp?r=111&TabName=Projects'
        }]
        return results
    except Exception as e:
        print(f"CAR search error: {e}")
        return []


def get_car_project(project_id):
    """Get CAR project - redirect to registry"""
    return {
        'projectId': project_id,
        'name': 'View on CAR Registry',
        'status': 'See registry for details',
        'registryUrl': f'https://thereserve2.apx.com/myModule/rpt/myrpt.asp?r=111&TabName=Projects'
    }
