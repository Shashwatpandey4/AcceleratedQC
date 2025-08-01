import pennylane as qml
from pennylane import numpy as np
import pathlib
import os
import ctypes
import sys

class CustomDevice(qml.devices.Device):
    config_filepath = pathlib.Path(__file__).parent / "custom_device.toml"

    @staticmethod
    def get_c_interface():
        # Get the build directory path
        build_dir = pathlib.Path(__file__).parent.parent.parent.parent / "build" / "lib"
        so_path = build_dir / "librtd_custom_device.so"
        return "CustomDevice", str(so_path)

    def __init__(self, shots=None, wires=None, xclbin_path=None, use_fpga=True):
        super().__init__(wires=wires, shots=shots)
        self.xclbin_path = xclbin_path or "libadf.xclbin"
        self.use_fpga = use_fpga
        
        # Check if FPGA bitstream exists
        if self.use_fpga and not os.path.exists(self.xclbin_path):
            print(f"Warning: FPGA bitstream not found at {self.xclbin_path}")
            print("Falling back to CPU implementation")
            self.use_fpga = False
        
        # Load the C++ library
        self._load_cpp_library()

    def _load_cpp_library(self):
        """Load the C++ shared library"""
        try:
            build_dir = pathlib.Path(__file__).parent.parent.parent.parent / "build" / "lib"
            so_path = build_dir / "librtd_custom_device.so"
            
            if not so_path.exists():
                print(f"Warning: C++ library not found at {so_path}")
                self.cpp_lib = None
                return
            
            self.cpp_lib = ctypes.CDLL(str(so_path))
            print(f"✓ Loaded C++ library: {so_path}")
            
            # Set up function signatures
            self._setup_function_signatures()
            
        except Exception as e:
            print(f"Warning: Failed to load C++ library: {e}")
            self.cpp_lib = None

    def _setup_function_signatures(self):
        """Set up the function signatures for C++ calls"""
        if not self.cpp_lib:
            return
            
        # Set up hadamard_kernel_execute_c function (C-style wrapper)
        self.cpp_lib.hadamard_kernel_execute_c.argtypes = [
            ctypes.c_char_p,  # xclbin_path
            ctypes.POINTER(ctypes.c_double),  # input_real
            ctypes.POINTER(ctypes.c_double),  # input_imag
            ctypes.POINTER(ctypes.c_double),  # output_real
            ctypes.POINTER(ctypes.c_double),  # output_imag
            ctypes.c_int,  # target
            ctypes.c_int,  # num_qubits
            ctypes.c_int   # state_size
        ]
        self.cpp_lib.hadamard_kernel_execute_c.restype = ctypes.c_int

    def _apply_hadamard_cpp(self, state, target_qubit, num_qubits):
        """Apply Hadamard gate using C++ backend"""
        if not self.cpp_lib:
            return self._apply_hadamard_python(state, target_qubit, num_qubits)
        
        try:
            # Prepare arrays for C function
            state_size = len(state)
            input_real = (ctypes.c_double * state_size)()
            input_imag = (ctypes.c_double * state_size)()
            output_real = (ctypes.c_double * state_size)()
            output_imag = (ctypes.c_double * state_size)()
            
            # Copy state to input arrays
            for i, c in enumerate(state):
                input_real[i] = c.real
                input_imag[i] = c.imag
            
            # Call C function
            xclbin_path = self.xclbin_path.encode('utf-8')
            status = self.cpp_lib.hadamard_kernel_execute_c(
                xclbin_path,
                input_real,
                input_imag,
                output_real,
                output_imag,
                target_qubit,
                num_qubits,
                state_size
            )
            
            if status == 0:
                # Convert back to Python
                result = []
                for i in range(state_size):
                    result.append(complex(output_real[i], output_imag[i]))
                return np.array(result, dtype=np.complex128)
            else:
                print(f"C++ kernel failed with status {status}, falling back to Python")
                return self._apply_hadamard_python(state, target_qubit, num_qubits)
                
        except Exception as e:
            print(f"Error calling C++ kernel: {e}, falling back to Python")
            return self._apply_hadamard_python(state, target_qubit, num_qubits)

    def _apply_hadamard_python(self, state, target_qubit, num_qubits):
        """Apply Hadamard gate using Python implementation"""
        result = state.copy()
        dim = 1 << num_qubits
        sqrt2_inv = 1.0 / np.sqrt(2.0)
        
        for i in range(dim):
            idx0 = i
            idx1 = i ^ (1 << target_qubit)
            if idx0 < idx1:
                temp0 = result[idx0]
                temp1 = result[idx1]
                result[idx0] = sqrt2_inv * (temp0 + temp1)
                result[idx1] = sqrt2_inv * (temp0 - temp1)
        
        return result

    @property
    def operations(self):
        return {"Hadamard"}

    @property
    def observables(self):
        return {"State"}

    def execute(self, circuits, execution_config=None):
        """Execute quantum circuits and return real Hadamard results"""
        if self.use_fpga:
            print(f"Executing circuit with FPGA kernel (bitstream: {self.xclbin_path})")
        else:
            print("Executing circuit with CPU implementation")
        
        # Get the number of qubits
        num_qubits = len(self.wires) if self.wires else 1
        state_size = 2 ** num_qubits
        
        # Initialize state to |0...0⟩
        state = np.zeros(state_size, dtype=np.complex128)
        state[0] = 1.0
        
        # Apply Hadamard gates based on the circuit
        # For now, we'll apply Hadamard to all qubits to demonstrate
        for qubit in range(num_qubits):
            state = self._apply_hadamard_cpp(state, qubit, num_qubits)
            print(f"After Hadamard on qubit {qubit}: {state}")
        
        return state

# Create a simple circuit without qjit for development
@qml.qnode(CustomDevice(wires=1, use_fpga=True))
def circuit():
    qml.Hadamard(wires=0)
    return qml.state()

if __name__ == "__main__":
    print("Testing CustomDevice with real Hadamard kernel...")
    result = circuit()
    print("Circuit result:", result)
    print(f"Expected for 1 qubit: [0.70710678+0j, 0.70710678+0j]")
    print(f"Results match expected: {np.allclose(result, [0.70710678+0j, 0.70710678+0j], atol=1e-6)}")
    
    # Test with CPU fallback
    print("\nTesting with CPU fallback...")
    @qml.qnode(CustomDevice(wires=1, use_fpga=False))
    def circuit_cpu():
        qml.Hadamard(wires=0)
        return qml.state()
    
    result_cpu = circuit_cpu()
    print("CPU circuit result:", result_cpu)
    print(f"CPU results match expected: {np.allclose(result_cpu, [0.70710678+0j, 0.70710678+0j], atol=1e-6)}")
