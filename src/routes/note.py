from flask import Blueprint, jsonify, request
from src.models.note import Note, db
from sqlalchemy import or_

note_bp = Blueprint('note', __name__)

@note_bp.route('/notes', methods=['GET'])
def get_notes():
    """Get all notes, ordered by most recently updated"""
    notes = Note.query.order_by(Note.updated_at.desc()).all()
    return jsonify([note.to_dict() for note in notes])

@note_bp.route('/notes', methods=['POST'])
def create_note():
    """Create a new note"""
    try:
        data = request.json
        if not data or 'title' not in data or 'content' not in data:
            return jsonify({'error': 'Title and content are required'}), 400
        # Accept tags as either a comma-separated string or a list of strings.
        tags = data.get('tags', '')
        if isinstance(tags, list):
            # join list into comma-separated string
            tags = ','.join([str(t).strip() for t in tags if t is not None])
        else:
            tags = str(tags).strip()

        note = Note(title=data['title'], content=data['content'], tags=tags)
        db.session.add(note)
        db.session.commit()
        return jsonify(note.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    """Get a specific note by ID"""
    note = Note.query.get_or_404(note_id)
    return jsonify(note.to_dict())

@note_bp.route('/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """Update a specific note"""
    try:
        note = Note.query.get_or_404(note_id)
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        # Update allowed fields; preserve existing values if not provided.
        note.title = data.get('title', note.title)
        note.content = data.get('content', note.content)

        if 'tags' in data:
            tags = data.get('tags')
            if isinstance(tags, list):
                tags = ','.join([str(t).strip() for t in tags if t is not None])
            else:
                tags = str(tags).strip()
            note.tags = tags
        db.session.commit()
        return jsonify(note.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """Delete a specific note"""
    try:
        note = Note.query.get_or_404(note_id)
        db.session.delete(note)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/search', methods=['GET'])
def search_notes():
    """Search notes by title or content"""
    # Support fuzzy, case-insensitive substring search on title or content.
    # Trim whitespace and return empty list for blank queries to avoid
    # returning all notes accidentally.
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify([])

    pattern = f"%{query}%"
    # Use ilike for case-insensitive matching (works on most DB backends).
    notes = Note.query.filter(
        (Note.title.ilike(pattern)) | (Note.content.ilike(pattern))
    ).order_by(Note.updated_at.desc()).all()

    return jsonify([note.to_dict() for note in notes])


@note_bp.route('/notes/tags', methods=['GET'])
def filter_notes_by_tags():
    """Filter notes by tag(s).

    Accepts either:
      - tags=query1,query2  (comma-separated string)
      - tag=value repeated, e.g. ?tag=one&tag=two

    Matches notes where the stored comma-separated tags contain any of
    the requested tags (case-insensitive substring match).
    """
    # Collect tags from repeated 'tag' params and from a single 'tags' param
    requested = []
    requested += [t.strip() for t in request.args.getlist('tag') if t and t.strip()]
    tags_param = request.args.get('tags')
    if tags_param:
        requested += [t.strip() for t in tags_param.split(',') if t.strip()]

    # Normalize and dedupe
    tags = []
    seen = set()
    for t in requested:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            tags.append(t)

    if not tags:
        return jsonify([])

    # Build OR filters: any note whose tags string contains one of the tags
    patterns = [Note.tags.ilike(f"%{t}%") for t in tags]
    notes = Note.query.filter(or_(*patterns)).order_by(Note.updated_at.desc()).all()

    return jsonify([note.to_dict() for note in notes])

