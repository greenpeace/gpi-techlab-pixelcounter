import os
import ast
import json
from datetime import datetime

from flask import (
    Blueprint,
    redirect,
    render_template,
    url_for,
    jsonify,
    request,
    flash
)

from utils.aigeneration import handle_openai
from system.getsecret import getsecrets
from system.setenv import project_id

from system.firstoredb import modules_ref
from system.firstoredb import groups_ref
# Check if Logged in
from modules.auth.auth import login_is_required

modulesblue = Blueprint('modules',
                        __name__,
                        template_folder='templates')


@modulesblue.route('/load_modules',
                   methods=['GET', 'POST'],
                   endpoint='load_modules')
@login_is_required
def load_modules():
    modules_dir = os.path.join(os.path.dirname(__file__), 'modules')
    for module_name in os.listdir(modules_dir):
        module_path = os.path.join(modules_dir, module_name)
        if os.path.isdir(module_path):
            module_json = os.path.join(module_path, 'module.json')
            if os.path.exists(module_json):
                with open(module_json, 'r') as f:
                    module_data = json.load(f)
                    modules_ref.document(module_name).set(module_data)


@modulesblue.route('/modules',
                   methods=['GET', 'POST'],
                   endpoint='list_modules')
@login_is_required
def list_modules():
    modules = modules_ref.stream()
    return render_template('modules/list.html', modules=modules)


@modulesblue.route('/modules/<module_name>/toggle',
                   methods=['POST'],
                   endpoint='toggle_module')
@login_is_required
def toggle_module(module_name):
    module_ref = modules_ref.document(module_name)
    module = module_ref.get().to_dict()
    module['enabled'] = not module.get('enabled', False)
    module_ref.update({'enabled': module['enabled']})
    return redirect(url_for('modules.list_modules'))


@modulesblue.route('/check-modules',
                   methods=['GET'],
                   endpoint="check_modules")
@login_is_required
def check_modules():
    modules_dir = 'modules'
    missing_files = []

    if os.path.exists(modules_dir):
        for subdir in os.listdir(modules_dir):
            module_path = os.path.join(modules_dir, subdir)
            if os.path.isdir(module_path):
                required_files = ["routes.py", "firestore_model.py", "templates", "static"]
                for file in required_files:
                    file_path = os.path.join(module_path, file)
                    if not os.path.exists(file_path):
                        missing_files.append({
                            "module": subdir,
                            "missing_file": file
                        })

    if missing_files:
        return jsonify(missing_files), 400
    else:
        return jsonify({"message": "All modules are set up correctly!"}), 200


@modulesblue.route('/manage_modules',
                   methods=['GET'],
                   endpoint="manage_modules")
@login_is_required
def manage_modules():
    # Get the path to the modules directory
    modules_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    modules = []

    if os.path.exists(modules_dir):
        for module_name in os.listdir(modules_dir):
            module_path = os.path.join(modules_dir, module_name)

            # Skip if not a directory or if it's the nested 'modules/modules'
            if not os.path.isdir(module_path) or module_name == "modules":
                continue

            module_json = os.path.join(module_path, 'module.json')
            if os.path.exists(module_json):
                with open(module_json, 'r') as f:
                    module_data = json.load(f)

                doc_ref = modules_ref.document(module_name)
                doc = doc_ref.get()

                module_data.setdefault('name', module_name)
                module_data.setdefault('active', True)
                module_data.setdefault('version', '1.0')

                if not doc.exists:
                    module_data['date_added'] = datetime.utcnow().isoformat()
                else:
                    existing_data = doc.to_dict()
                    module_data['date_added'] = existing_data.get('date_added', datetime.utcnow().isoformat())

                if not module_data.get('description'):
                    module_data['description'] = generate_module_description(
                        module_name, module_path, return_html=False
                    )
                    # Save the description back to module.json
                    try:
                        with open(module_json, 'w') as f:
                            json.dump(module_data, f, indent=2)
                    except Exception as e:
                        print(f"Failed to update module.json for {module_name}: {e}")

                doc_ref.set(module_data)

                modules.append({
                    "name": module_data['name'],
                    "active": module_data['active'],
                    "version": module_data['version'],
                    "date_added": module_data['date_added'],
                    "description": module_data['description']
                })

    return render_template('manage_modules.html', modules=modules)


def generate_module_description(module_name, module_path, return_html=False):
    """
        Generates a 50-word description of the module by analyzing the main Python file in the folder.
    """
    # Try to find the main Python file (same name as folder or first .py file)
    module_file = os.path.join(module_path, f"{module_name}.py")
    if not os.path.exists(module_file):
        # Fallback: pick the first .py file
        for fname in os.listdir(module_path):
            if fname.endswith('.py'):
                module_file = os.path.join(module_path, fname)
                break
        else:
            return "No Python file found to describe."

    try:
        with open(module_file, 'r') as f:
            lines = f.readlines()
            code_sample = ''.join(lines[:50])  # Only first 50 lines
    except Exception as e:
        return f"# Could not read module file: {str(e)}"

    # Prompt setup
    prompt = f"""Analyze the following Python code and write a technical module description
                (max 50 words) that explains what the module does in a web application context.
                ### Code:
                {code_sample}
            """

    systemrole = (
        "You are a technical documentation specialist working with software teams. "
        "Your role is to read source code and produce short, accurate, 50-word summaries of what each module does. "
        "Focus on functional purpose, key actions, and how it integrates in a web application. "
        "Do not repeat filenames or boilerplate."
    )

    try:
        api_key = getsecrets("openai_api_key", project_id)
        response = handle_openai(
            prompt,
            model_name="gpt-4o",
            systemrole=systemrole,
            api_key=api_key,
            return_html=return_html
        )
        return response.strip()
    except Exception as e:
        return f"Auto-description failed: {str(e)}"


@modulesblue.route('/review/<module_name>',
                   methods=['POST'],
                   endpoint="review_module")
@login_is_required
def review_module(module_name):
    try:
        # Get module path
        module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', module_name))
        if not os.path.exists(module_path):
            return jsonify({"error": "Module not found"}), 404

        # Collect all Python files in the module
        code_files = []
        for root, _, files in os.walk(module_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        code_files.append({
                            'name': os.path.relpath(file_path, module_path),
                            'content': f.read()
                        })

        if not code_files:
            return jsonify({"error": "No Python files found in module"}), 404

        # Create review directory in module if it doesn't exist
        reviews_dir = os.path.join(module_path, 'reviews')
        if not os.path.exists(reviews_dir):
            os.makedirs(reviews_dir)

        # Create timestamped review file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        review_file = os.path.join(reviews_dir, f'code_review_{timestamp}.md')

        # Prepare the prompt for code review
        prompt = f"""Please perform a comprehensive code review for the following Python module files.
        Focus on:
        1. Code quality and best practices
        2. Potential security issues
        3. Performance optimizations
        4. Error handling
        5. Documentation completeness

        Files to review:
        {[f['name'] for f in code_files]}

        Code content:
        """

        for file in code_files:
            prompt += f"\n\n--- {file['name']} ---\n{file['content']}"

        systemrole = """You are an expert Python code reviewer. Analyze the code and provide:
        1. A summary of findings
        2. Critical issues that need immediate attention
        3. Suggestions for improvements
        4. Best practices that should be implemented
        Please format the response in markdown."""

        # Call OpenAI for review
        api_key = getsecrets("openai_api_key", project_id)
        review_result = handle_openai(
            prompt,
            model_name="gpt-4",
            systemrole=systemrole,
            api_key=api_key,
            return_html=False  # Changed to False for markdown output
        )

        # Write review to file
        with open(review_file, 'w') as f:
            f.write(f"# Code Review: {module_name}\n\n")
            f.write(f"Review Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## Files Reviewed\n")
            for file in code_files:
                f.write(f"- {file['name']}\n")
            f.write("\n## Review Results\n\n")
            f.write(review_result)

        return jsonify({
            "status": "success",
            "message": f"Module {module_name} reviewed successfully!",
            "review_file": review_file,
            "review": review_result
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error reviewing module: {str(e)}"
        }), 500


# Example route for deleting a module
@modulesblue.route('/delete/<module_name>',
                   methods=['POST'],
                   endpoint="delete_module")
@login_is_required
def delete_module(module_name):
    try:
        # Get module path
        module_path = os.path.join('modules', module_name)

        # Check if module exists
        if not os.path.exists(module_path):
            return jsonify({"status": "error", "message": f"Module {module_name} not found!"}), 404

        # Delete Firestore data first
        doc_ref = modules_ref.document(module_name)

        # Delete all subcollections
        collections = ['reviews', 'docstring_checks', 'documentation']
        for collection in collections:
            subcoll_ref = doc_ref.collection(collection)
            docs = subcoll_ref.stream()
            for doc in docs:
                doc.reference.delete()

        # Delete the main document
        doc_ref.delete()

        # Delete physical files
        for root, dirs, files in os.walk(module_path, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(module_path)

        return jsonify({
            "status": "success",
            "message": f"Module {module_name} and all associated data deleted successfully!"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error deleting module: {str(e)}"
        }), 500


# Example route for checking docstrings
@modulesblue.route('/check-docstring/<module_name>',
                   methods=['POST'],
                   endpoint="check_docstring")
@login_is_required
def check_docstring(module_name):
    try:
        module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', module_name))
        if not os.path.exists(module_path):
            return jsonify({"error": "Module not found"}), 404

        docstring_report = []
        files_updated = []

        # Walk through all Python files in the module
        for root, _, files in os.walk(module_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        module_content = f.read()

                    try:
                        tree = ast.parse(module_content)
                        file_report = {
                            'file': os.path.relpath(file_path, module_path),
                            'missing_docstrings': [],
                            'has_docstrings': [],
                            'updated_functions': []
                        }

                        # Track positions where we need to insert docstrings
                        updates_needed = []

                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                                name = node.name
                                if ast.get_docstring(node) is None:
                                    # Generate docstring using OpenAI
                                    function_code = ast.unparse(node)
                                    api_key = getsecrets("openai_api_key", project_id)
                                    docstring = handle_openai(
                                        f"Generate a docstring for this Python {type(node).__name__}:\n{function_code}",
                                        model_name="gpt-4",
                                        systemrole="Generate clear, concise Python docstrings following Google style.",
                                        api_key=api_key,
                                        return_html=False
                                    )

                                    updates_needed.append({
                                        'node': node,
                                        'docstring': docstring
                                    })
                                    file_report['missing_docstrings'].append(name)
                                else:
                                    file_report['has_docstrings'].append(name)

                        # If we have updates, modify the file
                        if updates_needed:
                            with open(file_path, 'r') as f:
                                lines = f.readlines()

                            # Apply updates from bottom to top to preserve line numbers
                            for update in sorted(updates_needed, key=lambda x: x['node'].lineno, reverse=True):
                                indent = ' ' * update['node'].col_offset
                                docstring_lines = [f'{indent}"""{update["docstring"]}"""\n']
                                lines.insert(update['node'].lineno, ''.join(docstring_lines))
                                file_report['updated_functions'].append(update['node'].name)

                            # Write back to file
                            with open(file_path, 'w') as f:
                                f.writelines(lines)

                            files_updated.append(file_report['file'])

                        docstring_report.append(file_report)
                    except Exception as e:
                        docstring_report.append({
                            'file': os.path.relpath(file_path, module_path),
                            'error': str(e)
                        })

        # Calculate statistics
        total_functions = sum(len(r.get('missing_docstrings', [])) + len(r.get('has_docstrings', []))
                              for r in docstring_report)
        total_missing = sum(len(r.get('missing_docstrings', [])) for r in docstring_report)
        coverage = ((total_functions - total_missing) / total_functions * 100) if total_functions > 0 else 0

        return jsonify({
            "status": "success",
            "message": f"Docstring check and update completed for {module_name}",
            "coverage_percentage": round(coverage, 2),
            "files_updated": files_updated,
            "report": docstring_report,
            "summary": {
                "total_functions": total_functions,
                "missing_docstrings": total_missing,
                "has_docstrings": total_functions - total_missing,
                "files_modified": len(files_updated)
            }
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error checking and updating docstrings: {str(e)}"
        }), 500


# Example route for generating docs
@modulesblue.route('/generate-docs/<module_name>',
                   methods=['POST'],
                   endpoint="generate_docs")
@login_is_required
def generate_docs(module_name):
    try:
        module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', module_name))
        if not os.path.exists(module_path):
            return jsonify({"error": "Module not found"}), 404

        # Create docs directory if it doesn't exist
        docs_dir = 'docs'
        if not os.path.exists(docs_dir):
            os.makedirs(docs_dir)

        docs_path = os.path.join(docs_dir, f'{module_name}_docs.md')

        # Check if file exists and handle accordingly
        if os.path.exists(docs_path):
            # Backup existing file with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{docs_path}.{timestamp}.bak"
            os.rename(docs_path, backup_path)

        templates_path = os.path.join(module_path, 'templates')

        # Collect all Python files and their rendered templates
        routes_and_templates = []
        for root, _, files in os.walk(module_path):
            for file in files:
                if file.endswith('.py'):
                    with open(os.path.join(root, file), 'r') as f:
                        content = f.read()
                        # Find render_template calls
                        for line in content.split('\n'):
                            if 'render_template' in line:
                                try:
                                    # Handle different quote patterns
                                    if '"' in line:
                                        template_name = line.split('render_template(')[1].split('"')[1]
                                    elif "'" in line:
                                        template_name = line.split('render_template(')[1].split("'")[1]
                                    else:
                                        continue  # Skip if no quotes found

                                    routes_and_templates.append({
                                        'file': file,
                                        'template': template_name
                                    })
                                except (IndexError, Exception) as e:
                                    print(e)
                                    print(f"Warning: Could not parse template name in line: {line}")
                                    continue

        # Analyze templates for UI elements
        ui_elements = []
        if os.path.exists(templates_path):
            for template in os.listdir(templates_path):
                if template.endswith('.html'):
                    with open(os.path.join(templates_path, template), 'r') as f:
                        content = f.read()

                        # Prepare prompt for AI analysis
                        prompt = f"""Analyze this HTML template and describe
                        its purpose and functionality from a user's perspective.
                        Focus on:
                        1. What can users do on this page?
                        2. What forms and inputs are available?
                        3. What are the main features?
                        4. Any special instructions for users?

                        Template: {template}
                        Content:
                        {content}
                        """

                        systemrole = """You are a technical writer creating user-friendly documentation.
                        Explain features in simple terms that non-technical users can understand.
                        Focus on actions users can take and what they accomplish."""

                        # Get AI analysis
                        api_key = getsecrets("openai_api_key", project_id)
                        template_docs = handle_openai(
                            prompt,
                            model_name="gpt-4",
                            systemrole=systemrole,
                            api_key=api_key,
                            return_html=False
                        )

                        ui_elements.append({
                            'template': template,
                            'documentation': template_docs
                        })

        # Generate the documentation
        with open(docs_path, 'w') as f:
            f.write(f"# User Guide: {module_name}\n\n")

            # Overview section
            f.write("## Overview\n")
            f.write("This guide explains how to use the features and functionality ")
            f.write(f"available in the {module_name} module.\n\n")

            # Features and Pages section
            f.write("## Features and Pages\n\n")
            for ui in ui_elements:
                f.write(f"### {ui['template']}\n")
                f.write(f"{ui['documentation']}\n\n")

            # Navigation section
            f.write("## Navigation\n")
            f.write("The following pages are available in this module:\n\n")
            for route in routes_and_templates:
                f.write(f"- {route['template']}\n")

            # Save documentation metadata to Firestore
            doc_data = {
                'module_name': module_name,
                'generated_date': datetime.utcnow().isoformat(),
                'templates_analyzed': [ui['template'] for ui in ui_elements],
                'doc_path': docs_path
            }
            modules_ref.document(module_name).collection('documentation').add(doc_data)

        return jsonify({
            "status": "success",
            "message": f"User documentation generated for {module_name}",
            "path": docs_path
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error generating documentation: {str(e)}"
        }), 500


@modulesblue.route('/check_modules_in_app',
                   methods=['GET'],
                   endpoint="check_modules_in_app")
@login_is_required
def check_modules_in_app(app_file='app.py'):
    used_modules = []
    if os.path.exists(app_file):
        with open(app_file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith('from modules.') or line.startswith('import modules.'):
                    # Extract the module name from the import statement
                    module_name = line.split(' ')[1].split('.')[1]  # get the module name
                    used_modules.append(module_name)
    return used_modules


@modulesblue.route('/clean_up_unused_modules',
                   methods=['GET'],
                   endpoint="clean_up_unused_modules")
@login_is_required
def clean_up_unused_modules(modules_dir='modules', app_file='app.py'):
    # Get all modules in the system
    all_modules = [subdir for subdir in os.listdir(modules_dir) if os.path.isdir(os.path.join(modules_dir, subdir))]
    used_modules = check_modules_in_app(app_file)

    unused_modules = [module for module in all_modules if module not in used_modules]

    # Return the list of unused modules
    return unused_modules


@modulesblue.route('/check_syntax',
                   methods=['GET'],
                   endpoint="check_syntax")
@login_is_required
def check_syntax(file_path):
    try:
        with open(file_path, "r") as f:
            code = f.read()
        ast.parse(code)
        return {"file": file_path, "status": "Valid"}
    except SyntaxError as e:
        return {"file": file_path, "status": f"Syntax error: {e}"}
    except Exception as e:
        return {"file": file_path, "status": f"Error: {str(e)}"}


@modulesblue.route('/toggle-active/<module_name>',
                   methods=['POST'],
                   endpoint="toggle_active")
@login_is_required
def toggle_active(module_name):
    try:
        data = request.get_json()
        new_state = data.get('active', False)

        # Update Firestore
        doc_ref = modules_ref.document(module_name)
        doc = doc_ref.get()

        if not doc.exists:
            return jsonify({"error": "Module not found"}), 404

        # Update the active status
        doc_ref.update({
            'active': new_state,
            'last_modified': datetime.utcnow().isoformat()
        })

        return jsonify({
            "status": "success",
            "message": f"Module {module_name} {'activated' if new_state else 'deactivated'} successfully",
            "active": new_state
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error toggling module status: {str(e)}"
        }), 500


@modulesblue.route('/set_group_permissions',
                   methods=['GET', 'POST'],
                   endpoint='set_group_permissions')
@login_is_required
def set_group_permissions():
    if request.method == 'POST':
        group_id = request.form.get('group_id')
        module_permissions = request.form.get('module_permissions')

        try:
            # Parse the module permissions JSON
            permissions = json.loads(module_permissions)

            # Validate the permissions structure
            if not isinstance(permissions, dict):
                raise ValueError("Invalid permissions format")

            # Update group permissions in Firestore
            group_ref = groups_ref.document(group_id)
            group_ref.update({
                'module_permissions': permissions,
                'last_updated': datetime.utcnow().isoformat()
            })

            # Redirect back to group list with success message
            flash('Group permissions updated successfully', 'success')
            return redirect(url_for('groups.list_groups'))

        except Exception as e:
            flash(f'Error updating permissions: {str(e)}', 'danger')
            return redirect(url_for('groups.list_groups'))

    # GET request - return available modules and current permissions
    group_id = request.args.get('group_id')
    if not group_id:
        return jsonify({
            'status': 'error',
            'message': 'group_id parameter is required'
        }), 400

    # Get all modules
    modules = modules_ref.stream()
    module_list = [module.to_dict() for module in modules]

    # Get current permissions for the group
    group_ref = groups_ref.document(group_id)
    group_data = group_ref.get().to_dict()
    current_permissions = group_data.get('module_permissions', {})

    return render_template('set_group_permissions.html',
                           modules=module_list,
                           current_permissions=current_permissions,
                           group_id=group_id)
