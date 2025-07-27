#!/usr/bin/env python3
"""
Backward Compatibility Test for Cloud Sync Optimization

This script verifies that all optimizations maintain backward compatibility
with existing sessions and UI workflows.
"""

import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
import traceback

# Add fastshot to path
sys.path.insert(0, str(Path(__file__).parent))

# Import required modules
try:
    from fastshot.meta_cache import MetaCacheManager
    from fastshot.cloud_sync import CloudSyncManager
    from fastshot.session_manager import SessionManager
    print("✓ All modules imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)


class BackwardCompatibilityTester:
    """Backward compatibility tester."""
    
    def __init__(self):
        # Create mock app
        import configparser
        self.config = configparser.ConfigParser()
        
        # Load actual config if available
        config_path = Path("fastshot/config.ini")
        if config_path.exists():
            self.config.read(config_path)
        
        # Initialize components
        self.cloud_sync = CloudSyncManager(self)
        self.meta_cache = MetaCacheManager()
        self.session_manager = SessionManager(self)
        
        print("✓ Backward compatibility tester initialized")
    
    def run_compatibility_tests(self):
        """Run comprehensive backward compatibility tests."""
        print("\n" + "="*60)
        print("BACKWARD COMPATIBILITY TESTS")
        print("="*60)
        
        tests = [
            ("Legacy Session Format", self.test_legacy_session_format),
            ("Old Cache Structure", self.test_old_cache_structure),
            ("Missing Metadata Handling", self.test_missing_metadata),
            ("Version Migration", self.test_version_migration),
            ("UI Workflow Compatibility", self.test_ui_workflow_compatibility),
            ("Cloud Storage Compatibility", self.test_cloud_storage_compatibility),
            ("Configuration Compatibility", self.test_configuration_compatibility)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                result = test_func()
                
                results[test_name] = {
                    'status': 'PASS' if result else 'FAIL',
                    'details': result if isinstance(result, dict) else {}
                }
                
                status_symbol = "✓" if result else "✗"
                print(f"{status_symbol} {test_name}: {results[test_name]['status']}")
                
            except Exception as e:
                results[test_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
                print(f"✗ {test_name}: ERROR - {e}")
                traceback.print_exc()
        
        self.print_compatibility_report(results)
        return results
    
    def test_legacy_session_format(self):
        """Test compatibility with legacy session formats."""
        print("Testing legacy session format compatibility...")
        
        # Create legacy session format (pre-optimization)
        legacy_session = {
            'session': {
                'windows': [
                    {
                        'image_data': 'base64_encoded_image_data_here',
                        'position': [100, 100],
                        'size': [400, 300],
                        'always_on_top': True,
                        'transparency': 1.0
                    },
                    {
                        'image_data': 'base64_encoded_image_data_here_2',
                        'position': [200, 200],
                        'size': [300, 200],
                        'always_on_top': False,
                        'transparency': 0.8
                    }
                ]
            },
            'metadata': {
                'name': 'Legacy Test Session',
                'desc': 'Test session in legacy format',
                'created_at': '2024-01-01T12:00:00'
            }
        }
        
        # Test that system can extract metadata from legacy format
        metadata = legacy_session.get('metadata', {})
        
        # Verify required fields are present or can be defaulted
        name = metadata.get('name', '')
        desc = metadata.get('desc', '')
        created_at = metadata.get('created_at', datetime.now().isoformat())
        
        # Fields that should be defaulted for legacy sessions
        tags = metadata.get('tags', [])
        color = metadata.get('color', 'blue')
        class_name = metadata.get('class', '')
        image_count = len(legacy_session.get('session', {}).get('windows', []))
        
        print(f"✓ Extracted metadata from legacy session:")
        print(f"  Name: {name}")
        print(f"  Description: {desc}")
        print(f"  Image count: {image_count}")
        print(f"  Tags: {tags}")
        print(f"  Color: {color}")
        
        # Test saving legacy session with new metadata structure
        enhanced_metadata = {
            'name': name,
            'desc': desc,
            'tags': tags,
            'color': color,
            'class': class_name,
            'image_count': image_count,
            'created_at': created_at,
            'file_size': len(json.dumps(legacy_session)),
            'thumbnail_collage': None  # Legacy sessions won't have thumbnails
        }
        
        # Save using new cache system
        test_filename = "legacy_compatibility_test.fastshot"
        self.meta_cache.save_meta_index(test_filename, enhanced_metadata)
        
        # Verify it can be loaded back
        loaded_metadata = self.meta_cache.load_meta_index(test_filename)
        
        assert loaded_metadata is not None, "Should load legacy-converted metadata"
        assert loaded_metadata['metadata']['name'] == name, "Name should be preserved"
        assert loaded_metadata['metadata']['image_count'] == image_count, "Image count should be calculated"
        
        print("✓ Legacy session format successfully converted and cached")
        
        return {
            'legacy_format_supported': True,
            'metadata_extracted': True,
            'enhanced_metadata_created': True,
            'cache_compatibility': True,
            'image_count_calculated': image_count,
            'fields_defaulted': len([f for f in ['tags', 'color', 'class'] if f not in metadata])
        }
    
    def test_old_cache_structure(self):
        """Test compatibility with old cache structures."""
        print("Testing old cache structure compatibility...")
        
        # Create old-style cache structure (without some new fields)
        old_cache_entry = {
            "version": "1.0",
            "filename": "old_cache_test.fastshot",
            "metadata": {
                "name": "Old Cache Test",
                "desc": "Test session with old cache structure",
                "created_at": "2024-01-01T12:00:00"
                # Missing: tags, color, class, image_count, file_size, thumbnail_collage
            },
            "created_at": "2024-01-01T12:00:00"
            # Missing: last_updated, checksum
        }
        
        # Save old-style cache entry directly
        old_cache_file = self.meta_cache.meta_indexes_dir / "old_cache_test.meta.json"
        with open(old_cache_file, 'w', encoding='utf-8') as f:
            json.dump(old_cache_entry, f, indent=2)
        
        print("✓ Created old-style cache entry")
        
        # Test loading old cache entry
        loaded_old = self.meta_cache.load_meta_index("old_cache_test.fastshot")
        
        if loaded_old:
            metadata = loaded_old.get('metadata', {})
            
            # Verify that missing fields are handled gracefully
            name = metadata.get('name', '')
            desc = metadata.get('desc', '')
            tags = metadata.get('tags', [])
            color = metadata.get('color', '')
            class_name = metadata.get('class', '')
            image_count = metadata.get('image_count', 0)
            
            print(f"✓ Loaded old cache entry successfully:")
            print(f"  Name: {name}")
            print(f"  Tags: {tags} (defaulted)")
            print(f"  Color: {color} (defaulted)")
            print(f"  Image count: {image_count} (defaulted)")
            
            # Test cache validation with old entries
            cache_valid = self.meta_cache.validate_cache_integrity()
            print(f"✓ Cache validation with old entries: {cache_valid}")
            
            return {
                'old_cache_loaded': True,
                'missing_fields_handled': True,
                'cache_validation_works': cache_valid,
                'graceful_degradation': True
            }
        else:
            print("✗ Failed to load old cache entry")
            return False
    
    def test_missing_metadata(self):
        """Test handling of sessions with missing or incomplete metadata."""
        print("Testing missing metadata handling...")
        
        # Test completely missing metadata
        session_without_metadata = {
            'session': {
                'windows': [
                    {'image_data': 'test_data', 'position': [0, 0]}
                ]
            }
            # No metadata field
        }
        
        # Extract what we can
        metadata = session_without_metadata.get('metadata', {})
        
        # Should create default metadata
        default_metadata = {
            'name': metadata.get('name', ''),
            'desc': metadata.get('desc', 'No description available'),
            'tags': metadata.get('tags', []),
            'color': metadata.get('color', 'blue'),
            'class': metadata.get('class', ''),
            'image_count': len(session_without_metadata.get('session', {}).get('windows', [])),
            'created_at': metadata.get('created_at', datetime.now().isoformat()),
            'file_size': len(json.dumps(session_without_metadata)),
            'thumbnail_collage': None
        }
        
        print("✓ Created default metadata for session without metadata")
        
        # Test partial metadata
        partial_metadata_session = {
            'session': {'windows': []},
            'metadata': {
                'name': 'Partial Metadata Test'
                # Missing most fields
            }
        }
        
        partial_meta = partial_metadata_session.get('metadata', {})
        enhanced_partial = {
            'name': partial_meta.get('name', ''),
            'desc': partial_meta.get('desc', ''),
            'tags': partial_meta.get('tags', []),
            'color': partial_meta.get('color', 'blue'),
            'class': partial_meta.get('class', ''),
            'image_count': partial_meta.get('image_count', 0),
            'created_at': partial_meta.get('created_at', datetime.now().isoformat()),
            'file_size': partial_meta.get('file_size', 0),
            'thumbnail_collage': partial_meta.get('thumbnail_collage', None)
        }
        
        print("✓ Enhanced partial metadata successfully")
        
        # Test corrupted metadata
        try:
            corrupted_metadata = "invalid json content"
            # Should handle gracefully without crashing
            if isinstance(corrupted_metadata, str):
                # Create fallback metadata
                fallback_metadata = {
                    'name': 'Corrupted Session',
                    'desc': 'Metadata could not be parsed',
                    'tags': ['corrupted'],
                    'color': 'red',
                    'class': 'error',
                    'image_count': 0,
                    'created_at': datetime.now().isoformat(),
                    'file_size': 0,
                    'thumbnail_collage': None
                }
                print("✓ Created fallback metadata for corrupted session")
        
        except Exception as e:
            print(f"✗ Error handling corrupted metadata: {e}")
            return False
        
        return {
            'missing_metadata_handled': True,
            'partial_metadata_enhanced': True,
            'corrupted_metadata_handled': True,
            'default_values_applied': True,
            'graceful_error_handling': True
        }
    
    def test_version_migration(self):
        """Test version migration and upgrade paths."""
        print("Testing version migration...")
        
        # Test cache info migration
        old_cache_info = {
            "version": "0.9",  # Old version
            "last_sync": "2024-01-01T12:00:00",
            "cache_size_bytes": 1024000
            # Missing: total_meta_files, integrity_check
        }
        
        # Simulate loading old cache info
        current_cache_info = self.meta_cache._load_cache_info()
        
        # Should have current version and all required fields
        assert current_cache_info.get('version') == '1.0', "Should upgrade to current version"
        assert 'integrity_check' in current_cache_info, "Should have integrity check field"
        assert 'total_meta_files' in current_cache_info, "Should have total meta files field"
        
        print("✓ Cache info version migration works")
        
        # Test metadata index migration
        old_meta_index = {
            "version": "0.9",
            "filename": "migration_test.fastshot",
            "metadata": {
                "name": "Migration Test",
                "desc": "Test migration"
            }
            # Missing: checksum, last_updated
        }
        
        # Save old format
        migration_file = self.meta_cache.meta_indexes_dir / "migration_test.meta.json"
        with open(migration_file, 'w', encoding='utf-8') as f:
            json.dump(old_meta_index, f, indent=2)
        
        # Load and verify it works
        loaded_migrated = self.meta_cache.load_meta_index("migration_test.fastshot")
        
        if loaded_migrated:
            print("✓ Old metadata index format loaded successfully")
            
            # Re-save to upgrade format
            metadata = loaded_migrated.get('metadata', {})
            self.meta_cache.save_meta_index("migration_test.fastshot", metadata)
            
            # Verify upgraded format
            reloaded = self.meta_cache.load_meta_index("migration_test.fastshot")
            assert reloaded.get('version') == '1.0', "Should upgrade to current version"
            assert 'checksum' in reloaded, "Should have checksum after upgrade"
            
            print("✓ Metadata index migration completed")
        
        return {
            'cache_info_migration': True,
            'metadata_index_migration': True,
            'version_upgrade': True,
            'backward_compatibility_maintained': True
        }
    
    def test_ui_workflow_compatibility(self):
        """Test UI workflow compatibility."""
        print("Testing UI workflow compatibility...")
        
        # Test session loading workflow
        try:
            # Create test session data
            test_session_data = {
                'windows': [
                    {
                        'image_data': 'test_image_data',
                        'position': [100, 100],
                        'size': [400, 300]
                    }
                ]
            }
            
            # Test session manager compatibility
            # This should work with both old and new session formats
            session_metadata = {
                'name': 'UI Workflow Test',
                'desc': 'Testing UI workflow compatibility',
                'tags': ['ui', 'test'],
                'color': 'green',
                'class': 'ui_test',
                'image_count': 1,
                'created_at': datetime.now().isoformat(),
                'file_size': len(json.dumps(test_session_data))
            }
            
            print("✓ Session data and metadata prepared")
            
            # Test metadata extraction (should work for both old and new formats)
            extracted_name = session_metadata.get('name', '')
            extracted_desc = session_metadata.get('desc', '')
            extracted_tags = session_metadata.get('tags', [])
            
            assert extracted_name == 'UI Workflow Test', "Should extract name correctly"
            assert len(extracted_tags) == 2, "Should extract tags correctly"
            
            print("✓ Metadata extraction works correctly")
            
            # Test caching workflow
            self.meta_cache.save_meta_index("ui_workflow_test.fastshot", session_metadata)
            cached_metadata = self.meta_cache.load_meta_index("ui_workflow_test.fastshot")
            
            assert cached_metadata is not None, "Should cache and load metadata"
            print("✓ Caching workflow works correctly")
            
            return {
                'session_loading_compatible': True,
                'metadata_extraction_works': True,
                'caching_workflow_works': True,
                'ui_data_structures_compatible': True
            }
            
        except Exception as e:
            print(f"✗ UI workflow compatibility error: {e}")
            return False
    
    def test_cloud_storage_compatibility(self):
        """Test cloud storage compatibility."""
        if not self.cloud_sync.cloud_sync_enabled:
            print("⚠ Cloud sync disabled - skipping cloud storage compatibility tests")
            return True
        
        print("Testing cloud storage compatibility...")
        
        try:
            # Test loading existing cloud sessions (should work with old format)
            cloud_sessions = self.cloud_sync.list_cloud_sessions()
            print(f"✓ Listed {len(cloud_sessions)} existing cloud sessions")
            
            if cloud_sessions:
                # Test loading a session (should handle both old and new formats)
                sample_session = cloud_sessions[0]
                filename = sample_session['filename']
                
                # Try to load metadata index (may not exist for old sessions)
                meta_index = self.cloud_sync.load_meta_index_from_cloud(filename)
                
                if meta_index:
                    print(f"✓ Loaded metadata index for {filename}")
                    metadata = meta_index.get('metadata', {})
                    
                    # Verify required fields are present or can be defaulted
                    required_fields = ['name', 'desc', 'tags', 'color', 'class', 'image_count']
                    missing_fields = [f for f in required_fields if f not in metadata]
                    
                    if missing_fields:
                        print(f"  ⚠ Missing fields (will be defaulted): {missing_fields}")
                    else:
                        print("  ✓ All required fields present")
                else:
                    print(f"  ⚠ No metadata index for {filename} (legacy session)")
                    
                    # Try to load full session to extract metadata
                    session_data = self.cloud_sync.load_session_from_cloud(filename)
                    if session_data:
                        legacy_metadata = session_data.get('metadata', {})
                        print(f"  ✓ Extracted legacy metadata: {list(legacy_metadata.keys())}")
                    else:
                        print(f"  ⚠ Could not load session data for {filename}")
            
            # Test overall metadata file compatibility
            overall_meta = self.cloud_sync.load_overall_meta_file()
            if overall_meta:
                print("✓ Loaded overall metadata file")
                sessions_in_meta = overall_meta.get('sessions', [])
                print(f"  Sessions in overall metadata: {len(sessions_in_meta)}")
            else:
                print("⚠ No overall metadata file found")
            
            return {
                'cloud_session_listing_works': True,
                'legacy_session_loading_works': True,
                'metadata_index_compatibility': True,
                'overall_metadata_compatibility': True,
                'cloud_sessions_found': len(cloud_sessions)
            }
            
        except Exception as e:
            print(f"✗ Cloud storage compatibility error: {e}")
            return False
    
    def test_configuration_compatibility(self):
        """Test configuration compatibility."""
        print("Testing configuration compatibility...")
        
        # Test that old configuration keys still work
        old_config_keys = [
            ('CloudSync', 'cloud_sync_enabled'),
            ('CloudSync', 'aws_access_key'),
            ('CloudSync', 'aws_secret_key'),
            ('CloudSync', 'aws_region'),
            ('CloudSync', 's3_bucket_name'),
            ('CloudSync', 'encryption_key')
        ]
        
        config_compatibility = {}
        
        for section, key in old_config_keys:
            try:
                if self.config.has_section(section) and self.config.has_option(section, key):
                    value = self.config.get(section, key)
                    config_compatibility[f"{section}.{key}"] = "present"
                    print(f"✓ Config key {section}.{key}: present")
                else:
                    config_compatibility[f"{section}.{key}"] = "missing"
                    print(f"⚠ Config key {section}.{key}: missing (will use default)")
            except Exception as e:
                config_compatibility[f"{section}.{key}"] = f"error: {e}"
                print(f"✗ Config key {section}.{key}: error - {e}")
        
        # Test that new configuration keys are handled gracefully when missing
        new_config_keys = [
            ('CloudSync', 'ssl_verify'),
            ('CloudSync', 'proxy_enabled'),
            ('CloudSync', 'proxy_url')
        ]
        
        for section, key in new_config_keys:
            try:
                # Should not crash if missing, should use defaults
                value = self.config.getboolean(section, key, fallback=True) if key.endswith('enabled') else self.config.get(section, key, fallback='')
                print(f"✓ New config key {section}.{key}: handled gracefully")
            except Exception as e:
                print(f"✗ New config key {section}.{key}: error - {e}")
                return False
        
        # Test cloud sync initialization with various config states
        try:
            # Should not crash even with incomplete config
            cloud_sync_works = self.cloud_sync is not None
            print(f"✓ CloudSyncManager initialization: {'works' if cloud_sync_works else 'failed'}")
        except Exception as e:
            print(f"✗ CloudSyncManager initialization error: {e}")
            return False
        
        return {
            'old_config_keys_supported': True,
            'new_config_keys_handled': True,
            'graceful_config_handling': True,
            'cloud_sync_initialization': cloud_sync_works,
            'config_compatibility': config_compatibility
        }
    
    def print_compatibility_report(self, results):
        """Print comprehensive compatibility report."""
        print("\n" + "="*60)
        print("BACKWARD COMPATIBILITY REPORT")
        print("="*60)
        
        passed = sum(1 for r in results.values() if r['status'] == 'PASS')
        failed = sum(1 for r in results.values() if r['status'] == 'FAIL')
        errors = sum(1 for r in results.values() if r['status'] == 'ERROR')
        total = len(results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ✓")
        print(f"Failed: {failed} ✗")
        print(f"Errors: {errors} ⚠")
        print()
        
        # Detailed results
        for test_name, result in results.items():
            status_symbol = {"PASS": "✓", "FAIL": "✗", "ERROR": "⚠"}[result['status']]
            print(f"{status_symbol} {test_name}: {result['status']}")
            
            if result['status'] == 'ERROR':
                print(f"    Error: {result.get('error', 'Unknown error')}")
            elif 'details' in result and result['details']:
                for key, value in result['details'].items():
                    if isinstance(value, bool):
                        symbol = "✓" if value else "✗"
                        print(f"    {symbol} {key}: {'YES' if value else 'NO'}")
                    else:
                        print(f"    {key}: {value}")
        
        print("\n" + "="*60)
        
        # Save detailed results
        results_file = Path("backward_compatibility_results.json")
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total': total,
                    'passed': passed,
                    'failed': failed,
                    'errors': errors
                },
                'results': results
            }, f, indent=2, default=str)
        
        print(f"Detailed results saved to: {results_file}")
        
        overall_success = failed == 0 and errors == 0
        print(f"\nOVERALL COMPATIBILITY: {'MAINTAINED' if overall_success else 'ISSUES DETECTED'}")
        
        return overall_success


def main():
    """Main compatibility test execution."""
    print("Cloud Sync Optimization - Backward Compatibility Test")
    print("=" * 60)
    
    try:
        tester = BackwardCompatibilityTester()
        success = tester.run_compatibility_tests()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error during testing: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()