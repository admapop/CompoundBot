import re
from web3 import Web3
from constants import *
import time
from web3.middleware import geth_poa_middleware




def checkFormat(inputData, typeName):
	rex = re.compile(getattr(formats, typeName))
	assert rex.match(inputData), "Input is not the correct type only " + typeName +" is supported for this input."
	return inputData 

def decimal(value, decimals):
	return value/(10**decimals)


class blockChainInstance():
	def __init__(self, chainRPC, privatekey):
		self.web3 = Web3(Web3.HTTPProvider(chainRPC))
		self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
		self.senderAccount = self.web3.eth.account.privateKeyToAccount(privatekey)
		self.web3.eth.defaultAccount = self.senderAccount.address
		self.nonce = self.web3.eth.getTransactionCount(self.senderAccount.address)

	def smartTransact(self, params=[], contract=None, functionName=None):
		self.updateGasPrice()

		txn = contract.functions[functionName](*params).buildTransaction({'gas': 21000,
			'gasPrice': self.gas,
			'nonce': self.nonce,
			})
		estimatedgas = self.web3.eth.estimateGas({'from':self.web3.eth.defaultAccount,'to':txn['to'],'data':txn['data']})
		if estimatedgas > txn['gas']:
			txn['gas'] += int(estimatedgas*1.2)
		return txn

	def smartCall(self, params=[], contract=None, functionName=None):
		return contract.functions[functionName](*params).call()
	def contract(self, contractAddr, contractABI):
		return self.web3.eth.contract(address=checkFormat(contractAddr, 'address'), abi=contractABI)
	def updateGasPrice(self, price=10000000000):
		self.gas = price if self.web3.eth.gasPrice == 0 else self.web3.eth.gasPrice
	def signAndShip(self, txn):
		while True:
			try:
				txn = self.web3.eth.sendRawTransaction(self.web3.eth.account.signTransaction(txn, private_key=self.senderAccount.privateKey).rawTransaction)
				self.nonce += 1
				break
			except ValueError:
				self.nonce += 1
				txn['nonce'] = self.nonce
				continue

		BSC.waitForNextBlock()
		return txn
	def waitForNextBlock(self):
		block = self.web3.eth.getBlock('latest').number
		while True:
		 if self.web3.eth.getBlock('latest').number > block+2:
			 break
	def balance(self):
		return self.web3.eth.getBalance(self.senderAccount.address)
class formats():
    address = "^(0x)?(0X)?[0-9a-fA-F]{40}$"
        

class lpToken():
	def __init__(self, contractAddr, contractABI, blockchain):
		self.blockchain = blockchain
		self.contract = self.blockchain.contract(contractAddr, contractABI)
		self.token = [self.blockchain.smartCall(contract=self.contract,functionName='token0'), self.blockchain.smartCall(contract=self.contract,functionName='token1')]
		self.address = contractAddr

	def balanceOf(self, address):
		return self.blockchain.smartCall(contract=self.contract,functionName='balanceOf',params=[address])
	def getTokenBalances(self):
		return self.blockchain.smartCall(contract=self.contract,functionName='getReserves')
	def getTokenPrices(self):
		return self.blockchain.smartCall(contract=self.contract,functionName='price0CumulativeLast'), self.blockchain.smartCall(contract=self.contract,functionName='price1CumulativeLast')
	def getTotalSupply(self):
		return self.blockchain.smartCall(contract=self.contract,functionName='totalSupply')

class contract():
	def __init__(self,contractAddr, contractABI, blockchain):
		self.blockchain = blockchain
		self.contract = self.blockchain.contract(contractAddr, contractABI)
		self.address = contractAddr
	def smartCall(self, functionName, params=[]):
		return self.blockchain.smartCall(params, self.contract, functionName)
	def smartTransact(self, functionName, params=[]):
		return self.blockchain.signAndShip(self.blockchain.smartTransact(params, self.contract, functionName))


class dex():
	def __init__(self,contractAddr, contractABI, blockchain):
		self.blockchain = blockchain
		self.contract = self.blockchain.contract(contractAddr, contractABI)
		self.address = contractAddr
	def smartRoute(self):
		pass # will work on this later
	def smartSwap(self, amount, path, maxSlippage, eth=False): # will be smarter later when smartRoute is done
		sellValue = self.blockchain.smartCall(functionName='getAmountsOut',contract=self.contract, params=[ amount,path])[-1]
		buyValue = self.blockchain.smartCall(functionName='getAmountsIn',contract=self.contract, params=[sellValue ,path])[0]
		if eth:
			if path[-1] == '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c':
				return self.blockchain.signAndShip(self.blockchain.smartTransact([int(buyValue),int(sellValue*(1-(maxSlippage/100))),path,self.blockchain.web3.eth.defaultAccount, int(time.time())+300], self.contract, 'swapExactTokensForETH'))
			elif path[0] == '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c':
				return self.blockchain.signAndShip(self.blockchain.smartTransact([int(buyValue),int(sellValue*(1-(maxSlippage/100))),path,self.blockchain.web3.eth.defaultAccount, int(time.time())+300], self.contract, 'swapExactETHForTokens')) 
		else:
			return self.blockchain.signAndShip(self.blockchain.smartTransact([int(buyValue),int(sellValue*(1-(maxSlippage/100))),path,self.blockchain.web3.eth.defaultAccount, int(time.time())+300], self.contract, 'swapExactTokensForTokens'))
	def smartLiquidity(self, amount, tokenA, tokenB, maxSlippage, eth=False):
		amountB = self.blockchain.smartCall(functionName='getAmountsOut',contract=self.contract, params=[ amount,[tokenA, tokenB]])[-1]
		return self.blockchain.signAndShip(self.blockchain.smartTransact([tokenA, tokenB, amount, amountB, int(amount*(1-(maxSlippage/100))), int(amountB*(1-(maxSlippage/100))),self.blockchain.web3.eth.defaultAccount, int(time.time())+300], self.contract, 'addLiquidity'))

class token():
	def __init__(self,contractAddr, contractABI, blockchain):
		self.blockchain = blockchain
		self.contract = self.blockchain.contract(contractAddr, contractABI)
		self.address = contractAddr
	def balanceOf(self, address):
		return self.blockchain.smartCall(contract=self.contract,functionName='balanceOf', params=[self.blockchain.web3.eth.defaultAccount])

BSC = blockChainInstance("https://bsc-dataseed1.ninicoin.io/", '	')

SoupBNB = lpToken('0x284A5D8712C351Ca28417d131003120808dcE48B', ABI.pcsLPPair, BSC)
SoupsBNB = lpToken('0x6304Ae062c6bDf3D24Ac86374C7019A025443247', ABI.pcsLPPair, BSC)
SoupFarm = contract('0x12eFc306d0aDB92085025617F50B7F76D87385BF', ABI.soupFarm, BSC)
SoupsFarm = contract('0x034aF5a55e4316D975A29672733B9791c397b6AF', ABI.soupsFarm, BSC)
pcsRouter = dex('0x05fF2B0DB69458A0750badebc4f9e13aDd608C7F', ABI.pcsRouter, BSC)
soup = token('0x94F559aE621F1c810F31a6a620Ad7376776fe09E', ABI.erc20, BSC)
soups = token('0x69F27E70E820197A6e495219D9aC34C8C6dA7EeE', ABI.erc20, BSC)
wbnb = contract('0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', ABI.bnb, BSC)



## LOGIC ##
while True:
	accountBalance = 0
	accountBalance += ((decimal(SoupBNB.getTokenBalances()[1], 18)*decimal(SoupBNB.getTokenPrices()[1], 36))*2)  *  (decimal(SoupFarm.smartCall('balanceOf', [4, BSC.senderAccount.address])     ,18)/ decimal(SoupBNB.getTotalSupply(),18) )
	accountBalance += ((decimal(SoupBNB.getTokenBalances()[1], 18)*decimal(SoupBNB.getTokenPrices()[1], 36))*2)  *  (decimal(SoupsFarm.smartCall('balanceOf', [0, BSC.senderAccount.address])     ,18)/ decimal(SoupBNB.getTotalSupply(),18) )
	accountBalance += ((decimal(SoupsBNB.getTokenBalances()[1], 18)*decimal(SoupsBNB.getTokenPrices()[1], 36))*2)  *  (decimal(SoupsFarm.smartCall('balanceOf', [1, BSC.senderAccount.address])     ,18)/ decimal(SoupBNB.getTotalSupply(),18) )
	print('$' + str(accountBalance) )

	if BSC.web3.eth.getBlock('latest').number != 5093750:
		if decimal(SoupFarm.smartCall('pendingRewards', [4, BSC.senderAccount.address]),18) * (decimal(SoupBNB.getTokenPrices()[0], 36)) > accountBalance * 0.001:
			SoupFarm.smartTransact('deposit', [4, 0])
			pcsRouter.smartSwap(int(soup.balanceOf(BSC.senderAccount.address)*0.55), [soup.address, wbnb.address],0.5)
			pcsRouter.smartLiquidity(soup.balanceOf(BSC.senderAccount.address),soup.address, wbnb.address ,5)
			SoupFarm.smartTransact('deposit', [4, SoupBNB.balanceOf(BSC.senderAccount.address)])
			wbnb.smartTransact('withdraw',[wbnb.smartCall('balanceOf',[BSC.senderAccount.address])])
	else:
		if decimal(SoupFarm.smartCall('balanceOf', [4, BSC.senderAccount.address])     ,18) > 0:
			SoupFarm.smartTransact('withdraw', [4, SoupFarm.smartCall('balanceOf', [4, BSC.senderAccount.address])])
		if (decimal(SoupsFarm.smartCall('pendingRewards', [0, BSC.senderAccount.address]),18) * decimal(SoupBNB.getTokenPrices()[0], 36)) + ((decimal(SoupsFarm.smartCall('pendingRewards', [1, BSC.senderAccount.address]),18) * decimal(SoupsBNB.getTokenPrices()[0], 36))) > accountBalance * 0.001:
			SoupsFarm.smartTransact('deposit', [0, 0])
			SoupsFarm.smartTransact('deposit', [1, 0])
			pcsRouter.smartSwap(int(soups.balanceOf(BSC.senderAccount.address)*0.55), [soups.address, wbnb.address],0.5)
			pcsRouter.smartLiquidity(soups.balanceOf(BSC.senderAccount.address),soups.address, wbnb.address ,5)
			SoupsFarm.smartTransact('deposit', [1, SoupsBNB.balanceOf(BSC.senderAccount.address)])
			wbnb.smartTransact('withdraw',[wbnb.smartCall('balanceOf',[BSC.senderAccount.address])])