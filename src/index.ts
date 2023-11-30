import dotenvSafe from 'dotenv-safe'
import { ethers } from 'ethers'

dotenvSafe.config()

const provider = new ethers.JsonRpcProvider("http://localhost:8545")
const contract = new ethers.Contract(process.env.CONTRACT_ADDRESS, '[{"inputs":[],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":false,"inputs":[],"name":"Ping","type":"event"},{"anonymous":false,"inputs":[{"indexed":false,"internalType":"bytes32","name":"txHash","type":"bytes32"}],"name":"Pong","type":"event"},{"inputs":[],"name":"ping","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"pinger","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes32","name":"_txHash","type":"bytes32"}],"name":"pong","outputs":[],"stateMutability":"nonpayable","type":"function"}]', provider)

contract.on('ping', (event: any) => {
    console.log(event)
})