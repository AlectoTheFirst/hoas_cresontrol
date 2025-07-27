#!/usr/bin/env python3
"""
Final HACS compatibility validation for CresControl integration.
"""

import json
import os
from pathlib import Path

def validate_hacs_compatibility():
    """Validate HACS compatibility requirements."""
    
    print("HACS Compatibility Validation")
    print("=" * 40)
    
    issues = []
    
    # Check manifest.json
    manifest_path = Path("custom_components/crescontrol/manifest.json")
    if not manifest_path.exists():
        issues.append("❌ manifest.json not found")
        return issues
    
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Required fields for HACS
        required_fields = {
            "domain": str,
            "name": str, 
            "version": str,
            "documentation": str,
            "config_flow": bool,
            "dependencies": list,
            "requirements": list
        }
        
        for field, expected_type in required_fields.items():
            if field not in manifest:
                issues.append(f"❌ Missing required field: {field}")
            elif not isinstance(manifest[field], expected_type):
                issues.append(f"❌ Field {field} wrong type: {type(manifest[field])}, expected {expected_type}")
        
        # Check version format
        version = manifest.get("version", "")
        if not version or version == "0.0.1":
            issues.append("⚠️  Version should be updated from default")
        
        # Check HACS-specific fields
        if "iot_class" not in manifest:
            issues.append("⚠️  Missing iot_class (recommended)")
        
        if "integration_type" not in manifest:
            issues.append("⚠️  Missing integration_type (recommended)")
        
        # Check codeowners format
        codeowners = manifest.get("codeowners", [])
        if not codeowners:
            issues.append("⚠️  Missing codeowners")
        elif not all(owner.startswith("@") for owner in codeowners):
            issues.append("⚠️  Codeowners should start with @")
        
        print("✅ manifest.json validation passed")
        
    except json.JSONDecodeError as e:
        issues.append(f"❌ Invalid JSON in manifest.json: {e}")
    
    # Check required files
    base_path = Path("custom_components/crescontrol")
    required_files = ["__init__.py", "config_flow.py"]
    
    for file in required_files:
        if not (base_path / file).exists():
            issues.append(f"❌ Missing required file: {file}")
    
    # Check for common HACS issues
    if (base_path / "requirements.txt").exists():
        issues.append("⚠️  requirements.txt found - should use manifest.json requirements instead")
    
    # Check Python syntax
    python_files = list(base_path.glob("*.py"))
    syntax_errors = []
    
    for py_file in python_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                source = f.read()
            compile(source, str(py_file), 'exec')
        except SyntaxError as e:
            syntax_errors.append(f"{py_file.name}: {e}")
    
    if syntax_errors:
        issues.extend([f"❌ Syntax error: {error}" for error in syntax_errors])
    else:
        print("✅ Python syntax validation passed")
    
    return issues

def main():
    """Run HACS validation."""
    issues = validate_hacs_compatibility()
    
    print("\n" + "=" * 40)
    print("VALIDATION RESULTS")
    print("=" * 40)
    
    if not issues:
        print("\n✅ All HACS compatibility checks passed!")
        print("The integration should work with HACS.")
    else:
        print(f"\n⚠️  Found {len(issues)} issues:")
        for issue in issues:
            print(f"  {issue}")
    
    print("\n" + "=" * 40)
    print("HACS TROUBLESHOOTING")
    print("=" * 40)
    print("\nIf HACS shows version as commit hash (7246020):")
    print("1. Ensure the repository has proper Git tags")
    print("2. Check that the version in manifest.json matches a Git tag")
    print("3. HACS may need the repository to be properly tagged")
    print("4. Try reloading HACS or restarting Home Assistant")
    
    return len(issues)

if __name__ == "__main__":
    exit(main())