from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.conf import settings
from web3 import Web3
import ipfsapi
from tempfile import NamedTemporaryFile
from stories.rsa import generate_keypair, encrypt

from stories.forms import AddNewsForm, AddUserForm

w3 = Web3(Web3.HTTPProvider(settings.RPC_PROVIDER))
contract = w3.eth.contract(abi=settings.CONTRACT_ABI, address=settings.CONTRACT_ADDRESS)
ipfs = ipfsapi.connect(settings.IPFS_SERVER_ADDR, settings.IPFS_SERVER_PORT)

nullstrip = lambda x: x.rstrip('\x00')

def gethash(filepath):
    res = ipfs.add(filepath)
    return (res["Hash"][:24], res["Hash"][24:])

def getfilehash(filehash1,filehash2):
    filehash = zip(filehash1, filehash2)
    filehash = [nullstrip(x[0]) + nullstrip(x[1]) for x in filehash]
    return filehash

# Create your views here.
class HomePageView(View):
    def get(self, request):
        news = contract.call().getNews()
        newstext = list(map(ipfs.cat,getfilehash(news[0], news[1])))
        newsimage = getfilehash(news[2], news[3])
        news=zip(newstext,newsimage)
        news = [{"id":i,"text":x[0].decode('utf-8').partition('\n'),"image":x[1]} for i,x in enumerate(news)]
        return render(request, 'stories/homepage.html', {"news": news})

class ShowNewsView(View):
    def get(self, request, newsid):
        news = contract.call().oneNews(newsid)
        news = list(map(nullstrip, news))
        texthash=news[0]+news[1]
        imagehash=news[2]+news[3]
        text=ipfs.cat(texthash).decode('utf-8').partition('\n')
        return render(request, 'stories/shownews.html', {"title":text[0],"text":text[2], "image":imagehash})

class AddNewsView(View):
    def get(self, request):
        form = AddNewsForm()
        return render(request, 'stories/addnews.html', {"form": form})
    def post(self, request):
        form = AddNewsForm(request.POST, request.FILES)
        if form.is_valid():
            text=form.cleaned_data["text"]
            image=request.FILES["image"]
            privatekey=(form.cleaned_data["privatekey"],form.cleaned_data["private_n"])
            userid=form.cleaned_data['user_id']
            with NamedTemporaryFile("w") as textFile:
                textFile.write(text)
                textFile.flush()
                hash=gethash(textFile.name)
            with NamedTemporaryFile("wb") as imagefile:
                for chunk in image.chunks():
                    imagefile.write(chunk)
                imagefile.flush()
                hash2=gethash(imagefile.name)
            message="abcd"
            cipher=encrypt(privatekey, message)
            message=list(map(ord,message))
            contract.transact({"from":w3.eth.coinbase}).verify(hash[0], hash[1], hash2[0], hash2[1], message,cipher,userid,len(message),privatekey[1])
            return render(request, 'stories/addnews_success.html')
        return render(request, 'stories/addnews.html', {"form": form})

class AddUserView(View):
    def get(self, request):
        form = AddUserForm()
        return render(request, 'stories/adduser.html', {"form": form})
    def post(self, request):
        form = AddUserForm(request.POST)
        if form.is_valid():
            prime1=form.cleaned_data["prime1"]
            prime2=form.cleaned_data["prime2"]
            userid=form.cleaned_data["userid"]
            (privatekey, publickey)=generate_keypair(prime1, prime2)

            contract.transact({"from":w3.eth.coinbase}).createUser(userid, publickey[0])
            return render(request, 'stories/adduser_success.html', {"privatekey":privatekey,"publickey":publickey, "userid":userid})

        return render(request, 'stories/adduser.html', {"form": form})

class ImageView(View):
    def get(self, request, hash):
        imagedata=ipfs.cat(hash)
        return HttpResponse(imagedata, content_type="image/jpeg")
