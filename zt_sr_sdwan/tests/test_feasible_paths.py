from src.routing.feasible_paths import FeasiblePaths

def test_feasible_path_finding():
    E_f = {('0', '1'), ('1', '2'), ('2', '3')}
    
    # Test valid path
    paths = FeasiblePaths.find_paths('0', '3', E_f)
    assert len(paths) == 1
    assert paths[0] == ['0', '1', '2', '3']

    # Test path not found
    paths_none = FeasiblePaths.find_paths('0', '4', E_f)
    assert len(paths_none) == 0

    # Test empty edge set
    paths_empty = FeasiblePaths.find_paths('0', '3', set())
    assert len(paths_empty) == 0
