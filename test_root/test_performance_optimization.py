#!/usr/bin/env python3
"""
Performance Optimization Test for Cloud Sync

This script tests memory usage and network efficiency optimizations
for large session collections.
"""

import sys
import os
import time
import json
import threading
import psutil
from pathlib import Path
from datetime import datetime
import traceback

# Add fastshot to path
sys.path.insert(0, str(Path(__file__).parent))

# Import required modules
try:
    from fastshot.meta_cache import MetaCacheManager
    from fastshot.cloud_sync import CloudSyncManager
    from fastshot.async_operations import get_async_manager, CloudMetadataSyncOperation
    print("✓ All modules imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)


class PerformanceTester:
    """Performance optimization tester."""
    
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
        self.async_manager = get_async_manager()
        
        # Performance metrics
        self.metrics = {
            'memory_usage': [],
            'network_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'load_times': []
        }
        
        print("✓ Performance tester initialized")
    
    def run_performance_tests(self):
        """Run comprehensive performance tests."""
        print("\n" + "="*60)
        print("PERFORMANCE OPTIMIZATION TESTS")
        print("="*60)
        
        tests = [
            ("Memory Usage Baseline", self.test_memory_baseline),
            ("Cache Performance", self.test_cache_performance),
            ("Network Efficiency", self.test_network_efficiency),
            ("Large Dataset Handling", self.test_large_dataset),
            ("Concurrent Operations", self.test_concurrent_operations),
            ("Memory Leak Detection", self.test_memory_leaks),
            ("Optimization Effectiveness", self.test_optimization_effectiveness)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                start_time = time.time()
                result = test_func()
                duration = time.time() - start_time
                
                results[test_name] = {
                    'status': 'PASS' if result else 'FAIL',
                    'duration': duration,
                    'details': result if isinstance(result, dict) else {}
                }
                
                status_symbol = "✓" if result else "✗"
                print(f"{status_symbol} {test_name}: {results[test_name]['status']} ({duration:.2f}s)")
                
            except Exception as e:
                duration = time.time() - start_time
                results[test_name] = {
                    'status': 'ERROR',
                    'duration': duration,
                    'error': str(e)
                }
                print(f"✗ {test_name}: ERROR - {e}")
        
        self.print_performance_report(results)
        return results
    
    def test_memory_baseline(self):
        """Establish memory usage baseline."""
        print("Measuring baseline memory usage...")
        
        process = psutil.Process()
        baseline_memory = process.memory_info().rss / (1024 * 1024)
        
        # Record baseline
        self.metrics['memory_usage'].append({
            'timestamp': time.time(),
            'memory_mb': baseline_memory,
            'operation': 'baseline'
        })
        
        print(f"✓ Baseline memory usage: {baseline_memory:.2f} MB")
        
        return {
            'baseline_memory_mb': baseline_memory,
            'reasonable_baseline': baseline_memory < 100  # Should be under 100MB
        }
    
    def test_cache_performance(self):
        """Test cache performance and hit rates."""
        print("Testing cache performance...")
        
        # Clear cache to start fresh
        self.meta_cache.clear_cache()
        
        # Create test metadata entries
        test_sessions = []
        for i in range(20):
            filename = f"perf_test_{i:03d}.fastshot"
            metadata = {
                'name': f'Performance Test {i}',
                'desc': f'Test session {i} for performance testing',
                'tags': ['performance', 'test', f'batch_{i//5}'],
                'color': ['blue', 'red', 'green', 'yellow'][i % 4],
                'class': f'test_class_{i%3}',
                'image_count': i * 2,
                'created_at': datetime.now().isoformat(),
                'file_size': 1024 * (i + 1)
            }
            
            self.meta_cache.save_meta_index(filename, metadata)
            test_sessions.append(filename)
        
        print(f"✓ Created {len(test_sessions)} test metadata entries")
        
        # Test cache loading performance
        start_time = time.time()
        cached_metadata = self.meta_cache.get_cached_metadata()
        cache_load_time = time.time() - start_time
        
        print(f"✓ Cache loading time: {cache_load_time:.3f}s for {len(cached_metadata)} entries")
        
        # Test individual metadata loading (should be fast)
        individual_load_times = []
        for filename in test_sessions[:5]:  # Test first 5
            start_time = time.time()
            metadata = self.meta_cache.load_meta_index(filename)
            load_time = time.time() - start_time
            individual_load_times.append(load_time)
            
            if metadata:
                self.metrics['cache_hits'] += 1
            else:
                self.metrics['cache_misses'] += 1
        
        avg_individual_load = sum(individual_load_times) / len(individual_load_times)
        print(f"✓ Average individual metadata load time: {avg_individual_load:.4f}s")
        
        # Test cache validation performance
        start_time = time.time()
        cache_valid = self.meta_cache.validate_cache_integrity()
        validation_time = time.time() - start_time
        
        print(f"✓ Cache validation time: {validation_time:.3f}s, valid: {cache_valid}")
        
        return {
            'cache_entries_created': len(test_sessions),
            'cache_load_time': cache_load_time,
            'avg_individual_load_time': avg_individual_load,
            'validation_time': validation_time,
            'cache_valid': cache_valid,
            'performance_targets': {
                'fast_bulk_loading': cache_load_time < 1.0,  # Under 1 second
                'fast_individual_loading': avg_individual_load < 0.01,  # Under 10ms
                'fast_validation': validation_time < 2.0  # Under 2 seconds
            }
        }
    
    def test_network_efficiency(self):
        """Test network efficiency and request optimization."""
        if not self.cloud_sync.cloud_sync_enabled:
            print("⚠ Cloud sync disabled - skipping network efficiency tests")
            return True
        
        print("Testing network efficiency...")
        
        # Count network requests (approximate)
        initial_requests = self.metrics['network_requests']
        
        # Test efficient session listing (should be single request)
        start_time = time.time()
        cloud_sessions = self.cloud_sync.list_cloud_sessions()
        list_time = time.time() - start_time
        
        print(f"✓ Listed {len(cloud_sessions)} cloud sessions in {list_time:.3f}s")
        
        # Test metadata loading efficiency
        if cloud_sessions:
            sample_sessions = cloud_sessions[:3]  # Test first 3 sessions
            
            metadata_load_times = []
            for session in sample_sessions:
                filename = session['filename']
                
                start_time = time.time()
                meta_index = self.cloud_sync.load_meta_index_from_cloud(filename)
                load_time = time.time() - start_time
                metadata_load_times.append(load_time)
                
                if meta_index:
                    print(f"  ✓ Loaded metadata for {filename} in {load_time:.3f}s")
                else:
                    print(f"  ⚠ No metadata index for {filename}")
            
            avg_metadata_load = sum(metadata_load_times) / len(metadata_load_times) if metadata_load_times else 0
            print(f"✓ Average metadata load time: {avg_metadata_load:.3f}s")
        
        # Test overall metadata loading
        start_time = time.time()
        overall_meta = self.cloud_sync.load_overall_meta_file()
        overall_load_time = time.time() - start_time
        
        if overall_meta:
            print(f"✓ Loaded overall metadata in {overall_load_time:.3f}s")
        else:
            print("⚠ No overall metadata file found")
        
        return {
            'session_list_time': list_time,
            'avg_metadata_load_time': avg_metadata_load if cloud_sessions else 0,
            'overall_meta_load_time': overall_load_time,
            'cloud_sessions_found': len(cloud_sessions),
            'network_efficiency': {
                'fast_listing': list_time < 5.0,  # Under 5 seconds
                'fast_metadata_loading': avg_metadata_load < 2.0 if cloud_sessions else True,  # Under 2 seconds
                'fast_overall_loading': overall_load_time < 3.0  # Under 3 seconds
            }
        }
    
    def test_large_dataset(self):
        """Test handling of large session collections."""
        print("Testing large dataset handling...")
        
        # Simulate large dataset by creating many cache entries
        large_dataset_size = 100
        
        print(f"Creating {large_dataset_size} simulated sessions...")
        
        start_time = time.time()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)
        
        # Create large dataset
        for i in range(large_dataset_size):
            filename = f"large_test_{i:04d}.fastshot"
            metadata = {
                'name': f'Large Dataset Test {i}',
                'desc': f'Large dataset test session {i} with extended description to simulate real-world metadata size',
                'tags': [f'large_test', f'batch_{i//10}', f'category_{i%5}', 'performance'],
                'color': ['blue', 'red', 'green', 'yellow', 'purple'][i % 5],
                'class': f'large_test_class_{i%7}',
                'image_count': (i % 20) + 1,
                'created_at': datetime.now().isoformat(),
                'file_size': 1024 * 1024 * ((i % 10) + 1),  # 1-10 MB files
                'thumbnail_collage': f'base64_encoded_thumbnail_data_{i}' * 10  # Simulate thumbnail data
            }
            
            self.meta_cache.save_meta_index(filename, metadata)
            
            # Check memory usage periodically
            if i % 20 == 0:
                current_memory = process.memory_info().rss / (1024 * 1024)
                memory_increase = current_memory - initial_memory
                print(f"  Progress: {i}/{large_dataset_size}, Memory: +{memory_increase:.2f} MB")
        
        creation_time = time.time() - start_time
        final_memory = process.memory_info().rss / (1024 * 1024)
        memory_increase = final_memory - initial_memory
        
        print(f"✓ Created {large_dataset_size} entries in {creation_time:.2f}s")
        print(f"✓ Memory increase: {memory_increase:.2f} MB")
        
        # Test loading performance with large dataset
        start_time = time.time()
        all_cached = self.meta_cache.get_cached_metadata()
        load_time = time.time() - start_time
        
        print(f"✓ Loaded {len(all_cached)} entries in {load_time:.3f}s")
        
        # Test cache validation with large dataset
        start_time = time.time()
        cache_valid = self.meta_cache.validate_cache_integrity()
        validation_time = time.time() - start_time
        
        print(f"✓ Validated cache in {validation_time:.3f}s, valid: {cache_valid}")
        
        return {
            'dataset_size': large_dataset_size,
            'creation_time': creation_time,
            'memory_increase_mb': memory_increase,
            'load_time': load_time,
            'validation_time': validation_time,
            'entries_loaded': len(all_cached),
            'large_dataset_performance': {
                'reasonable_creation_time': creation_time < 30.0,  # Under 30 seconds
                'reasonable_memory_increase': memory_increase < 50.0,  # Under 50 MB
                'fast_loading': load_time < 2.0,  # Under 2 seconds
                'fast_validation': validation_time < 10.0  # Under 10 seconds
            }
        }
    
    def test_concurrent_operations(self):
        """Test concurrent operation handling."""
        print("Testing concurrent operations...")
        
        if not self.async_manager:
            print("⚠ Async manager not available")
            return True
        
        # Submit multiple concurrent operations
        operation_ids = []
        
        def test_operation(operation_id, duration):
            time.sleep(duration)
            return {"operation_id": operation_id, "completed": True}
        
        # Submit 5 concurrent operations
        for i in range(5):
            op_id = self.async_manager.submit_operation(
                test_operation,
                f"concurrent_op_{i}",
                0.5,  # 0.5 second duration
                operation_name=f"Concurrent Test {i}"
            )
            operation_ids.append(op_id)
        
        print(f"✓ Submitted {len(operation_ids)} concurrent operations")
        
        # Wait for all operations to complete
        start_time = time.time()
        completed_operations = []
        
        for op_id in operation_ids:
            result = self.async_manager.wait_for_operation(op_id, timeout=5.0)
            if result and result['status'] == 'completed':
                completed_operations.append(op_id)
        
        completion_time = time.time() - start_time
        
        print(f"✓ {len(completed_operations)}/{len(operation_ids)} operations completed in {completion_time:.2f}s")
        
        # Test memory optimization
        initial_ops = len(self.async_manager.get_all_operations())
        self.async_manager.optimize_memory_usage()
        final_ops = len(self.async_manager.get_all_operations())
        
        print(f"✓ Memory optimization: {initial_ops} -> {final_ops} operations")
        
        return {
            'operations_submitted': len(operation_ids),
            'operations_completed': len(completed_operations),
            'completion_time': completion_time,
            'operations_before_cleanup': initial_ops,
            'operations_after_cleanup': final_ops,
            'concurrent_performance': {
                'all_completed': len(completed_operations) == len(operation_ids),
                'reasonable_completion_time': completion_time < 2.0,  # Should complete in parallel
                'memory_optimization_effective': final_ops <= initial_ops
            }
        }
    
    def test_memory_leaks(self):
        """Test for memory leaks during repeated operations."""
        print("Testing for memory leaks...")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)
        
        memory_samples = []
        
        # Perform repeated operations
        for iteration in range(10):
            # Create and destroy cache entries
            for i in range(10):
                filename = f"leak_test_{iteration}_{i}.fastshot"
                metadata = {
                    'name': f'Leak Test {iteration}-{i}',
                    'desc': 'Memory leak test session',
                    'tags': ['leak_test'],
                    'color': 'blue',
                    'class': 'leak_test',
                    'image_count': 1,
                    'created_at': datetime.now().isoformat(),
                    'file_size': 1024
                }
                
                self.meta_cache.save_meta_index(filename, metadata)
                loaded = self.meta_cache.load_meta_index(filename)
            
            # Load cached metadata
            cached = self.meta_cache.get_cached_metadata()
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Sample memory usage
            current_memory = process.memory_info().rss / (1024 * 1024)
            memory_samples.append(current_memory)
            
            if iteration % 3 == 0:
                print(f"  Iteration {iteration}: {current_memory:.2f} MB (+{current_memory - initial_memory:.2f} MB)")
        
        final_memory = memory_samples[-1]
        memory_increase = final_memory - initial_memory
        
        # Check for memory leak (significant continuous increase)
        if len(memory_samples) >= 5:
            recent_trend = memory_samples[-3:]
            trend_increase = recent_trend[-1] - recent_trend[0]
            stable_memory = trend_increase < 5.0  # Less than 5MB increase in recent samples
        else:
            stable_memory = True
        
        print(f"✓ Memory leak test completed")
        print(f"  Initial: {initial_memory:.2f} MB")
        print(f"  Final: {final_memory:.2f} MB")
        print(f"  Increase: {memory_increase:.2f} MB")
        print(f"  Stable: {stable_memory}")
        
        return {
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'memory_increase_mb': memory_increase,
            'memory_samples': memory_samples,
            'stable_memory': stable_memory,
            'leak_detection': {
                'no_significant_leak': memory_increase < 20.0,  # Under 20MB increase
                'stable_recent_usage': stable_memory
            }
        }
    
    def test_optimization_effectiveness(self):
        """Test effectiveness of optimization features."""
        print("Testing optimization effectiveness...")
        
        # Test cache optimization
        cache_stats_before = self.meta_cache.get_cache_stats()
        
        # Perform cache cleanup
        cleanup_results = self.meta_cache.cleanup_cache_with_validation()
        
        cache_stats_after = self.meta_cache.get_cache_stats()
        
        print(f"✓ Cache cleanup completed: {cleanup_results.get('success', False)}")
        print(f"  Files validated: {cleanup_results.get('files_validated', 0)}")
        print(f"  Files deleted: {cleanup_results.get('files_deleted', 0)}")
        
        # Test async manager optimization
        async_stats_before = self.async_manager.get_memory_stats()
        self.async_manager.optimize_memory_usage()
        async_stats_after = self.async_manager.get_memory_stats()
        
        print(f"✓ Async manager optimization completed")
        print(f"  Operations before: {async_stats_before.get('total_operations', 0)}")
        print(f"  Operations after: {async_stats_after.get('total_operations', 0)}")
        
        return {
            'cache_cleanup_success': cleanup_results.get('success', False),
            'cache_files_validated': cleanup_results.get('files_validated', 0),
            'cache_files_deleted': cleanup_results.get('files_deleted', 0),
            'async_ops_before': async_stats_before.get('total_operations', 0),
            'async_ops_after': async_stats_after.get('total_operations', 0),
            'optimization_effective': {
                'cache_cleanup_works': cleanup_results.get('success', False),
                'async_optimization_works': async_stats_after.get('total_operations', 0) <= async_stats_before.get('total_operations', 0)
            }
        }
    
    def print_performance_report(self, results):
        """Print comprehensive performance report."""
        print("\n" + "="*60)
        print("PERFORMANCE OPTIMIZATION REPORT")
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
        
        # Performance summary
        print("PERFORMANCE SUMMARY:")
        print("-" * 40)
        
        for test_name, result in results.items():
            status_symbol = {"PASS": "✓", "FAIL": "✗", "ERROR": "⚠"}[result['status']]
            print(f"{status_symbol} {test_name}: {result['status']} ({result['duration']:.2f}s)")
            
            # Show key performance metrics
            if 'details' in result and result['details']:
                details = result['details']
                
                if 'performance_targets' in details:
                    targets = details['performance_targets']
                    for target, met in targets.items():
                        target_symbol = "✓" if met else "✗"
                        print(f"    {target_symbol} {target}: {'MET' if met else 'NOT MET'}")
                
                # Show key metrics
                key_metrics = ['baseline_memory_mb', 'cache_load_time', 'memory_increase_mb', 
                              'completion_time', 'dataset_size']
                for metric in key_metrics:
                    if metric in details:
                        print(f"    {metric}: {details[metric]}")
        
        print("\n" + "="*60)
        
        # Save detailed results
        results_file = Path("performance_test_results.json")
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total': total,
                    'passed': passed,
                    'failed': failed,
                    'errors': errors
                },
                'results': results,
                'metrics': self.metrics
            }, f, indent=2, default=str)
        
        print(f"Detailed results saved to: {results_file}")
        
        overall_success = failed == 0 and errors == 0
        print(f"\nOVERALL PERFORMANCE: {'OPTIMIZED' if overall_success else 'NEEDS IMPROVEMENT'}")
        
        return overall_success


def main():
    """Main performance test execution."""
    print("Cloud Sync Optimization - Performance Test")
    print("=" * 60)
    
    try:
        tester = PerformanceTester()
        success = tester.run_performance_tests()
        
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