add_subdirectory(null_qubit)
configure_file(null_qubit/null_qubit.toml null_qubit.toml)

add_subdirectory(custom_device)
configure_file(custom_device/custom_device.toml custom_device.toml)

if(ENABLE_OQD)
add_subdirectory(oqd)
configure_file(oqd/oqd.toml oqd.toml)
endif()

if(ENABLE_OPENQASM)
add_subdirectory(openqasm)
configure_file(openqasm/braket_local_qubit.toml braket_local_qubit.toml)
configure_file(openqasm/braket_aws_qubit.toml braket_aws_qubit.toml)
endif()
